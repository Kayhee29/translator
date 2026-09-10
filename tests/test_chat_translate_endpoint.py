from unittest.mock import Mock, patch
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


client = TestClient(app.app)


def test_chat_translate_requires_api_key():
    response = client.post(
        "/chat_translate",
        json={
            "target_language": "Vietnamese",
            "messages": [{"id": "m1", "role": "role_a", "content": "你好"}],
            "message_ids_to_translate": ["m1"],
        },
    )

    assert response.status_code == 401


def test_chat_translate_rejects_empty_target_language():
    response = client.post(
        "/chat_translate",
        headers={"x-api-key": "test-key"},
        json={
            "target_language": "",
            "messages": [{"id": "m1", "role": "role_a", "content": "你好"}],
            "message_ids_to_translate": ["m1"],
        },
    )

    assert response.status_code == 400


def test_chat_translate_rejects_unknown_message_ids():
    response = client.post(
        "/chat_translate",
        headers={"x-api-key": "test-key"},
        json={
            "target_language": "Vietnamese",
            "messages": [{"id": "m1", "role": "role_a", "content": "你好"}],
            "message_ids_to_translate": ["m2"],
        },
    )

    assert response.status_code == 400


def test_chat_translate_rejects_empty_messages():
    response = client.post(
        "/chat_translate",
        headers={"x-api-key": "test-key"},
        json={
            "target_language": "Vietnamese",
            "messages": [],
            "message_ids_to_translate": ["m1"],
        },
    )

    assert response.status_code == 400


def test_chat_translate_rejects_non_contiguous_message_ids():
    response = client.post(
        "/chat_translate",
        headers={"x-api-key": "test-key"},
        json={
            "target_language": "Vietnamese",
            "messages": [
                {"id": "m1", "role": "role_a", "content": "one"},
                {"id": "m2", "role": "role_b", "content": "two"},
                {"id": "m3", "role": "role_a", "content": "three"},
            ],
            "message_ids_to_translate": ["m1", "m3"],
        },
    )

    assert response.status_code == 400


def test_chat_translate_returns_translations_for_requested_ids():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"results":['
                        '{"id":"m1","translated_text":"Xin chao","source_language":"Chinese"},'
                        '{"id":"m2","translated_text":"How much?","source_language":"Vietnamese"}'
                        ']}'
                    )
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "messages": [
                    {"id": "m1", "role": "role_a", "content": "你好"},
                    {"id": "m2", "role": "role_b", "content": "Bao nhieu tien?"},
                ],
                "message_ids_to_translate": ["m1", "m2"],
            },
        )

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == "m1"
    assert response.json()["results"][1]["translated_text"] == "How much?"


def test_chat_translate_accepts_out_of_order_upstream_results_but_preserves_id_mapping():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"results":['
                        '{"id":"m2","translated_text":"How much?","source_language":"Vietnamese"},'
                        '{"id":"m1","translated_text":"Xin chao","source_language":"Chinese"}'
                        ']}'
                    )
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "messages": [
                    {"id": "m1", "role": "role_a", "content": "你好"},
                    {"id": "m2", "role": "role_b", "content": "Bao nhieu tien?"},
                ],
                "message_ids_to_translate": ["m1", "m2"],
            },
        )

    assert response.status_code == 200
    results_by_id = {item["id"]: item["translated_text"] for item in response.json()["results"]}
    assert results_by_id["m1"] == "Xin chao"
    assert results_by_id["m2"] == "How much?"


def test_chat_translate_rejects_invalid_json_from_upstream():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [{"message": {"content": "not-json"}}]
    }

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "Vietnamese",
                "messages": [{"id": "m1", "role": "role_a", "content": "你好"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500


def test_chat_translate_rejects_missing_ids_from_upstream():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"results":[{"id":"m1","translated_text":"Xin chao","source_language":"Chinese"}]}'
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "messages": [
                    {"id": "m1", "role": "role_a", "content": "你好"},
                    {"id": "m2", "role": "role_b", "content": "Bao nhieu tien?"},
                ],
                "message_ids_to_translate": ["m1", "m2"],
            },
        )

    assert response.status_code == 500
