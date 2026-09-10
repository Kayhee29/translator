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


def test_list_models_requires_api_key():
    response = client.get("/models")
    assert response.status_code == 401


def test_list_models_returns_normalized_models():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "data": [
            {"id": "gemini-3.8-flash-high"},
            {"id": "gemini-3-flash", "name": "Gemini 3 Flash"},
        ]
    }
    mocked_response.raise_for_status = Mock()

    with patch("app.requests.get", return_value=mocked_response) as mock_get:
        response = client.get("/models", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    assert response.json() == {
        "models": [
            {"id": "gemini-3.8-flash-high", "name": "gemini-3.8-flash-high"},
            {"id": "gemini-3-flash", "name": "Gemini 3 Flash"},
        ]
    }
    mock_get.assert_called_once()
    call_args, call_kwargs = mock_get.call_args
    assert call_args[0].endswith("/v1/models")
    assert call_kwargs["headers"] == {"Authorization": "Bearer test-key"}


def test_list_models_returns_502_on_malformed_model_data():
    mocked_response = Mock()
    mocked_response.json.return_value = {"data": [{"name": "missing-id"}]}
    mocked_response.raise_for_status = Mock()

    with patch("app.requests.get", return_value=mocked_response):
        response = client.get("/models", headers={"x-api-key": "test-key"})

    assert response.status_code == 502


def test_list_models_returns_502_on_upstream_failure():
    import requests

    with patch("app.requests.get", side_effect=requests.RequestException("connection failed")):
        response = client.get("/models", headers={"x-api-key": "test-key"})

    assert response.status_code == 502


def test_chat_translate_rejects_empty_model():
    response = client.post(
        "/chat_translate",
        headers={"x-api-key": "test-key"},
        json={
            "target_language": "English",
            "model": "   ",
            "messages": [{"id": "m1", "role": "role_a", "content": "你好"}],
            "message_ids_to_translate": ["m1"],
        },
    )
    assert response.status_code == 400


def test_chat_translate_forwards_model_and_returns_back_translation():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"results":['
                        '{"id":"m1","translated_text":"Hello","source_language":"Vietnamese","back_translated_text":"Xin chào"}'
                        ']}'
                    )
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response) as mock_post:
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "model": "gemini-3.8-flash-high",
                "verify_back_translation": True,
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 200
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["model"] == "gemini-3.8-flash-high"
    assert response.json()["results"][0]["back_translated_text"] == "Xin chào"


def test_chat_translate_omitted_model_uses_gemini_3_flash():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"results":['
                        '{"id":"m1","translated_text":"Hello","source_language":"Vietnamese"}'
                        ']}'
                    )
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response) as mock_post:
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 200
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["model"] == "gemini-3-flash"
    assert response.json()["results"][0]["back_translated_text"] == ""


def test_chat_translate_rejects_non_string_back_translation():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"results":['
                        '{"id":"m1","translated_text":"Hello","source_language":"Vietnamese","back_translated_text":123}'
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
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500


def test_chat_translate_normalizes_null_back_translation():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"results":['
                        '{"id":"m1","translated_text":"Hello","source_language":"Vietnamese","back_translated_text":null}'
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
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 200
    assert response.json()["results"][0]["back_translated_text"] == ""


def test_chat_translate_rejects_upstream_failure():
    import requests

    with patch("app.requests.post", side_effect=requests.RequestException("timeout")):
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500


def test_chat_translate_rejects_missing_choices_from_upstream():
    mocked_response = Mock()
    mocked_response.json.return_value = {"error": "upstream overload"}

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/chat_translate",
            headers={"x-api-key": "test-key"},
            json={
                "target_language": "English",
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500


def test_chat_translate_rejects_non_list_results():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"results":"not-a-list"}'
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
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500


def test_chat_translate_rejects_non_dict_result_item():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"results":["string-item"]}'
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
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500


def test_chat_translate_rejects_missing_translated_text():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"results":[{"id":"m1"}]}'
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
                "messages": [{"id": "m1", "role": "role_a", "content": "Xin chào"}],
                "message_ids_to_translate": ["m1"],
            },
        )

    assert response.status_code == 500
