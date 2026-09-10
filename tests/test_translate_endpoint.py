from unittest.mock import Mock, patch
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


client = TestClient(app.app)


def test_translate_requires_api_key():
    response = client.post("/translate", json={"text": "Xin chào"})
    assert response.status_code == 401


def test_translate_rejects_empty_model():
    response = client.post(
        "/translate",
        headers={"x-api-key": "test-key"},
        json={"text": "Xin chào", "model": "   "},
    )
    assert response.status_code == 400


def test_translate_rejects_empty_target_language():
    response = client.post(
        "/translate",
        headers={"x-api-key": "test-key"},
        json={"text": "Xin chào", "target_language": "   "},
    )
    assert response.status_code == 400


def test_translate_forwards_selected_model_and_verify_flag_and_returns_structured_response():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"result":"Hello","source_language":"Vietnamese","back_translated_text":"Xin chào"}'
                    )
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response) as mock_post:
        response = client.post(
            "/translate",
            headers={"x-api-key": "test-key"},
            json={
                "text": "Xin chào",
                "target_language": "English",
                "model": "gemini-3.8-flash-high",
                "verify_back_translation": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "result": "Hello",
        "source_language": "Vietnamese",
        "back_translated_text": "Xin chào",
    }
    mock_post.assert_called_once()
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["model"] == "gemini-3.8-flash-high"
    prompt_content = sent_payload["messages"][0]["content"]
    assert "English" in prompt_content
    assert "back_translated_text" in prompt_content


def test_translate_omitted_model_uses_gemini_3_flash_agent():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"result":"Hello","source_language":"Vietnamese","back_translated_text":""}'
                    )
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response) as mock_post:
        response = client.post(
            "/translate",
            headers={"x-api-key": "test-key"},
            json={
                "text": "Xin chào",
                "target_language": "English",
            },
        )

    assert response.status_code == 200
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["model"] == "gemini-3-flash-agent"


def test_translate_omitted_target_language_preserves_backward_compatibility():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "你好"
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response) as mock_post:
        response = client.post(
            "/translate",
            headers={"x-api-key": "test-key"},
            json={"text": "Xin chào"},
        )

    assert response.status_code == 200
    assert response.json() == {"result": "你好"}
    sent_payload = mock_post.call_args[1]["json"]
    assert sent_payload["model"] == "gemini-3-flash-agent"
    assert "specialized Vietnamese-Chinese translator" in sent_payload["messages"][0]["content"]


def test_translate_handles_markdown_code_fences():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "```json\n" + '{"result":"Hello","source_language":"Vietnamese","back_translated_text":""}\n```'
                }
            }
        ]
    }

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/translate",
            headers={"x-api-key": "test-key"},
            json={
                "text": "Xin chào",
                "target_language": "English",
            },
        )

    assert response.status_code == 200
    assert response.json()["result"] == "Hello"


def test_translate_rejects_invalid_json_when_target_language_provided():
    mocked_response = Mock()
    mocked_response.json.return_value = {
        "choices": [{"message": {"content": "not-valid-json"}}]
    }

    with patch("app.requests.post", return_value=mocked_response):
        response = client.post(
            "/translate",
            headers={"x-api-key": "test-key"},
            json={
                "text": "Xin chào",
                "target_language": "English",
            },
        )

    assert response.status_code == 500
