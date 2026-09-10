# Chat Translate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a context-aware `POST /chat_translate` API and bulk-paste normalization helpers that support multi-message chat translation into a user-selected target language with reduced context window token usage.

**Architecture:** Extend the existing FastAPI service in `app.py` with new Pydantic request/response models, pure helper functions for bulk-paste splitting, context extraction, and prompt generation, plus a new endpoint that reuses the existing Antigravity-compatible translation backend. Keep the first implementation backend-focused because no frontend files exist in this folder.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, requests, TinyDB-compatible project conventions, pytest for new tests

---

## File Structure

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\app.py`
- Create: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_helpers.py`
- Create: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_endpoint.py`
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\requirements.txt`

`app.py` will hold the first version because the project already centralizes all FastAPI logic there. Helper functions should still be kept in focused sections so they can be extracted later without rewriting behavior.

### Task 1: Test Harness Setup

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\requirements.txt`
- Create: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_helpers.py`
- Create: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_endpoint.py`

- [x] **Step 1: Add test dependencies**

Update `requirements.txt` to include:

```txt
fastapi==0.115.0
uvicorn==0.34.0
pydantic==2.9.2
tinydb==4.8.2
requests==2.32.3
pytest==8.3.3
httpx==0.27.2
```

- [x] **Step 2: Write the failing helper tests**

Create `tests/test_chat_translate_helpers.py`:

```python
from app import (
    build_reduced_context_window,
    build_chat_translate_prompt,
    split_bulk_paste_into_messages,
)


def test_build_reduced_context_window_includes_targets_and_prior_messages():
    messages = [
        {"id": "m1", "role": "role_a", "content": "A1"},
        {"id": "m2", "role": "role_b", "content": "B1"},
        {"id": "m3", "role": "role_a", "content": "A2"},
        {"id": "m4", "role": "role_b", "content": "B2"},
        {"id": "m5", "role": "role_a", "content": "A3"},
        {"id": "m6", "role": "role_b", "content": "B3"},
    ]

    result = build_reduced_context_window(
        messages=messages,
        message_ids_to_translate=["m6"],
        prior_limit=3,
    )

    assert [item["id"] for item in result] == ["m3", "m4", "m5", "m6"]


def test_build_chat_translate_prompt_mentions_target_language_and_ids():
    prompt = build_chat_translate_prompt(
        target_language="Vietnamese",
        context_messages=[
            {"id": "m1", "role": "role_a", "content": "Hello"},
            {"id": "m2", "role": "role_b", "content": "Xin chao"},
        ],
        message_ids_to_translate=["m2"],
    )

    assert "Vietnamese" in prompt
    assert "m2" in prompt
    assert "role_b" in prompt


def test_split_bulk_paste_into_messages_uses_blank_lines():
    messages = split_bulk_paste_into_messages(
        text="first message\n\nsecond message\n\n\nthird message",
        role="role_a",
        id_prefix="bulk",
    )

    assert [item["id"] for item in messages] == ["bulk-1", "bulk-2", "bulk-3"]
    assert [item["content"] for item in messages] == [
        "first message",
        "second message",
        "third message",
    ]


def test_split_bulk_paste_into_messages_supports_windows_newlines():
    messages = split_bulk_paste_into_messages(
        text="first message\r\n\r\nsecond message\r\n \r\nthird message",
        role="role_a",
        id_prefix="bulk",
    )

    assert [item["content"] for item in messages] == [
        "first message",
        "second message",
        "third message",
    ]
```

- [x] **Step 3: Write the failing endpoint tests**

Create `tests/test_chat_translate_endpoint.py`:

```python
from fastapi.testclient import TestClient
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
```

- [x] **Step 4: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_chat_translate_helpers.py tests/test_chat_translate_endpoint.py -v
```

Expected:

- FAIL because `build_reduced_context_window` does not exist
- FAIL because `build_chat_translate_prompt` does not exist
- FAIL because `/chat_translate` does not exist

- [x] **Step 5: Commit**

If git is available in the real implementation workspace:

```bash
git add requirements.txt tests/test_chat_translate_helpers.py tests/test_chat_translate_endpoint.py
git commit -m "test: add chat translate test scaffold"
```

If git is not available, skip the commit and continue.

### Task 2: Add Request Models and Pure Helpers

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\app.py`
- Test: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_helpers.py`

- [x] **Step 1: Add the failing validation and helper implementation**

Insert into `app.py` near the other request models and helper sections:

```python
import re


class ChatTranslateMessage(BaseModel):
    id: str
    role: str
    content: str


class ChatTranslateRequest(BaseModel):
    target_language: str
    messages: list[ChatTranslateMessage]
    message_ids_to_translate: list[str]


def split_bulk_paste_into_messages(text, role, id_prefix="bulk"):
    chunks = [chunk.strip() for chunk in re.split(r"\r?\n\s*\r?\n+", text) if chunk.strip()]
    return [
        {"id": f"{id_prefix}-{index}", "role": role, "content": chunk}
        for index, chunk in enumerate(chunks, start=1)
    ]


def build_reduced_context_window(messages, message_ids_to_translate, prior_limit=5):
    id_to_index = {message["id"]: index for index, message in enumerate(messages)}
    missing_ids = [message_id for message_id in message_ids_to_translate if message_id not in id_to_index]
    if missing_ids:
        raise ValueError(f"Unknown message ids: {missing_ids}")

    target_indexes = sorted(id_to_index[message_id] for message_id in message_ids_to_translate)
    if target_indexes[-1] - target_indexes[0] + 1 > len(target_indexes):
        raise ValueError("message_ids_to_translate must form a contiguous block")
    start_index = max(0, target_indexes[0] - prior_limit)
    end_index = target_indexes[-1] + 1
    return messages[start_index:end_index]


def build_chat_translate_prompt(target_language, context_messages, message_ids_to_translate):
    conversation_lines = []
    for message in context_messages:
        conversation_lines.append(
            f"[{message['id']}] role={message['role']}\n{message['content']}"
        )

    conversation_block = "\n\n".join(conversation_lines)
    ids_block = ", ".join(message_ids_to_translate)

    return (
        "You are a context-aware translator.\n"
        f"Translate only these message ids: {ids_block}\n"
        f"Target language: {target_language}\n"
        "Use the nearby conversation context to preserve meaning, tone, and references.\n"
        "Return ONLY valid JSON in the form "
        '{"results":[{"id":"message-id","translated_text":"...","source_language":"..."}]}\n\n'
        f"Conversation:\n{conversation_block}"
    )
```

- [x] **Step 2: Run helper tests**

Run:

```powershell
pytest tests/test_chat_translate_helpers.py -v
```

Expected:

- PASS for reduced context window behavior
- PASS for prompt content assertions

- [x] **Step 3: Tighten helper tests with validation edge cases**

Append to `tests/test_chat_translate_helpers.py`:

```python
import pytest


def test_build_reduced_context_window_raises_for_unknown_message_id():
    messages = [{"id": "m1", "role": "role_a", "content": "Hello"}]

    with pytest.raises(ValueError):
        build_reduced_context_window(
            messages=messages,
            message_ids_to_translate=["missing"],
            prior_limit=5,
        )


def test_build_reduced_context_window_raises_for_non_contiguous_targets():
    messages = [
        {"id": "m1", "role": "role_a", "content": "one"},
        {"id": "m2", "role": "role_b", "content": "two"},
        {"id": "m3", "role": "role_a", "content": "three"},
    ]

    with pytest.raises(ValueError):
        build_reduced_context_window(
            messages=messages,
            message_ids_to_translate=["m1", "m3"],
            prior_limit=2,
        )


def test_split_bulk_paste_into_messages_discards_empty_segments():
    messages = split_bulk_paste_into_messages(
        text="\n\nfirst\n\n   \n\nsecond\n\n",
        role="role_b",
        id_prefix="paste",
    )

    assert messages == [
        {"id": "paste-1", "role": "role_b", "content": "first"},
        {"id": "paste-2", "role": "role_b", "content": "second"},
    ]
```

- [x] **Step 4: Run helper tests again**

Run:

```powershell
pytest tests/test_chat_translate_helpers.py -v
```

Expected:

- PASS with 8 passing tests

- [x] **Step 5: Commit**

If git is available in the real implementation workspace:

```bash
git add app.py tests/test_chat_translate_helpers.py
git commit -m "feat: add chat translate helper functions"
```

If git is not available, skip the commit and continue.

### Task 3: Add Endpoint Validation and Request Flow

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\app.py`
- Test: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_endpoint.py`

- [x] **Step 1: Expand endpoint tests before implementation**

Append to `tests/test_chat_translate_endpoint.py`:

```python
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
```

- [ ] **Step 2: Implement request validation and real endpoint skeleton**

Add to `app.py`:

```python
@app.post("/chat_translate")
def chat_translate(request: ChatTranslateRequest, x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui long nhap Key")

    if not request.target_language or not request.target_language.strip():
        raise HTTPException(status_code=400, detail="target_language is required")

    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    if not request.message_ids_to_translate:
        raise HTTPException(status_code=400, detail="message_ids_to_translate must not be empty")

    normalized_messages = []
    for message in request.messages:
        if not message.id.strip():
            raise HTTPException(status_code=400, detail="message id must not be empty")
        if not message.content.strip():
            raise HTTPException(status_code=400, detail="message content must not be empty")
        normalized_messages.append(
            {"id": message.id, "role": message.role.strip() or "role_a", "content": message.content}
        )

    try:
        context_messages = build_reduced_context_window(
            messages=normalized_messages,
            message_ids_to_translate=request.message_ids_to_translate,
            prior_limit=5,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    prompt = build_chat_translate_prompt(
        target_language=request.target_language.strip(),
        context_messages=context_messages,
        message_ids_to_translate=request.message_ids_to_translate,
    )

    return {"results": []}
```

- [x] **Step 3: Run endpoint tests**

Run:

```powershell
pytest tests/test_chat_translate_endpoint.py -v
```

Expected:

- PASS for API key validation
- PASS for target language validation
- PASS for empty message validation
- PASS for unknown message ID validation
- PASS for non-contiguous message ID validation

- [x] **Step 4: Add response-shape expectation for the skeleton route**

Append to `tests/test_chat_translate_endpoint.py`:

```python
def test_chat_translate_returns_results_shape_before_upstream_integration():
    response = client.post(
        "/chat_translate",
        headers={"x-api-key": "test-key"},
        json={
            "target_language": "Vietnamese",
            "messages": [{"id": "m1", "role": "role_a", "content": "你好"}],
            "message_ids_to_translate": ["m1"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"results": []}
```

- [x] **Step 5: Commit**

If git is available in the real implementation workspace:

```bash
git add app.py tests/test_chat_translate_endpoint.py
git commit -m "feat: add chat translate request validation"
```

If git is not available, skip the commit and continue.

### Task 4: Integrate Translation Backend

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\app.py`
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_endpoint.py`

- [x] **Step 1: Write the failing success-path endpoint test with mocked upstream**

Append to `tests/test_chat_translate_endpoint.py`:

```python
from unittest.mock import Mock, patch


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
```

- [x] **Step 2: Replace placeholder endpoint body with real upstream call**

Update the route in `app.py` to:

```python
    antigravity_url = os.getenv(
        "ANTIGRAVITY_URL",
        "http://host.docker.internal:8045/v1/chat/completions",
    )

    payload = {
        "model": "gemini-3-flash",
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            antigravity_url,
            json=payload,
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=90,
        )
        api_response = response.json()
        if "choices" not in api_response:
            raise HTTPException(status_code=500, detail=f"Antigravity API Error: {api_response}")

        result_text = api_response["choices"][0]["message"]["content"].strip()
        translated_payload = json.loads(result_text)
        results = translated_payload.get("results")

        if not isinstance(results, list):
            raise HTTPException(status_code=500, detail="Invalid translation response format")

        returned_ids = {item.get("id") for item in results}
        missing_ids = [message_id for message_id in request.message_ids_to_translate if message_id not in returned_ids]
        if missing_ids:
            raise HTTPException(status_code=500, detail=f"Missing translated ids: {missing_ids}")

        for item in results:
            if not item.get("id") or not item.get("translated_text"):
                raise HTTPException(status_code=500, detail="Each translation result must include id and translated_text")

        return {"results": results}
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI did not return valid JSON")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [x] **Step 3: Add malformed upstream response coverage**

Append to `tests/test_chat_translate_endpoint.py`:

```python
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
```

- [x] **Step 4: Run the endpoint tests**

Run:

```powershell
pytest tests/test_chat_translate_endpoint.py -v
```

Expected:

- PASS for validation tests
- PASS for mocked success path
- PASS for out-of-order result mapping check
- PASS for invalid upstream JSON failure
- PASS for missing translated ID failure

- [x] **Step 5: Commit**

If git is available in the real implementation workspace:

```bash
git add app.py tests/test_chat_translate_endpoint.py
git commit -m "feat: add chat translate endpoint"
```

If git is not available, skip the commit and continue.

### Task 5: Final Verification and Documentation Check

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\app.py`
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_helpers.py`
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\tests\test_chat_translate_endpoint.py`

- [x] **Step 1: Add one full reduced-context behavior test**

Append to `tests/test_chat_translate_helpers.py`:

```python
def test_build_reduced_context_window_keeps_contiguous_slice_for_multiple_targets():
    messages = [
        {"id": "m1", "role": "role_a", "content": "one"},
        {"id": "m2", "role": "role_b", "content": "two"},
        {"id": "m3", "role": "role_a", "content": "three"},
        {"id": "m4", "role": "role_b", "content": "four"},
        {"id": "m5", "role": "role_a", "content": "five"},
    ]

    result = build_reduced_context_window(
        messages=messages,
        message_ids_to_translate=["m4", "m5"],
        prior_limit=2,
    )

    assert [item["id"] for item in result] == ["m2", "m3", "m4", "m5"]
```

- [x] **Step 2: Run the full test suite**

Run:

```powershell
pytest -v
```

Expected:

- PASS for all chat translate tests

- [x] **Step 3: Run a manual smoke test**

Run the server:

```powershell
uvicorn app:app --host 0.0.0.0 --port 8000
```

Then send a sample request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat_translate -Headers @{ "x-api-key" = "test-key" } -ContentType "application/json" -Body '{
  "target_language": "Vietnamese",
  "messages": [
    {"id": "m1", "role": "role_a", "content": "你好，商品还在吗？"},
    {"id": "m2", "role": "role_b", "content": "Con nhe, ban muon xem them anh khong?"},
    {"id": "m3", "role": "role_a", "content": "Cho minh xin gia cuoi cung"}
  ],
  "message_ids_to_translate": ["m1", "m2", "m3"]
}'
```

Expected:

- HTTP 200
- response contains a `results` array with ids `m1`, `m2`, `m3`

- [x] **Step 4: Inspect for scope drift**

Confirm the implementation only adds:

- new models
- bulk paste normalization helper logic
- reduced-context helper logic
- prompt builder
- `/chat_translate` endpoint
- tests and test dependencies

Do not add:

- TinyDB session persistence
- frontend assets
- summary memory logic
- per-message target language selection

- [x] **Step 5: Commit**

If git is available in the real implementation workspace:

```bash
git add app.py requirements.txt tests
git commit -m "feat: add context-aware chat translation API"
```

If git is not available, skip the commit and continue.
