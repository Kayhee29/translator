# Configurable Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add endpoint-backed language/model selection and optional Vietnamese back-translation verification to both translation modes without breaking existing API callers.

**Architecture:** Keep the browser talking only to FastAPI. Add a FastAPI `/models` proxy that discovers models from the configured OpenAI-compatible endpoint, extend translation payloads with optional settings, and centralize frontend settings/cache/payload logic in `index.html`. The backend accepts omitted `model` fields for compatibility and uses the existing endpoint-specific defaults; the new UI requires successful model discovery before enabling translation.

**Tech Stack:** FastAPI, Pydantic, requests, TinyDB, vanilla JavaScript, Tailwind CDN, pytest, FastAPI TestClient.

---

## File map

- Modify `app.py`: request models, model URL/normalization helpers, `/models`, translation prompts/parsers, `/translate`, and `/chat_translate`.
- Modify `tests/test_chat_translate_helpers.py`: model URL, model normalization, and chat prompt tests.
- Modify `tests/test_chat_translate_endpoint.py`: `/models` and chat settings tests.
- Create `tests/test_translate_endpoint.py`: quick translation settings and back-translation tests.
- Modify `index.html`: shared settings controls, model discovery/cache, payloads, and inline verify rendering.
- Modify `docs/superpowers/specs/2026-09-10-configurable-translation-design.md`: resolve the omitted-model compatibility rule.

## Task 1: Clarify compatibility in the spec

**Files:** `docs/superpowers/specs/2026-09-10-configurable-translation-design.md`

- [ ] Replace the conflicting validation wording with: “The browser UI requires a successfully discovered model before enabling translation. For backward compatibility, API callers that omit `model` use the existing endpoint-specific default. A supplied empty `model` is rejected with `400`.”
- [ ] Keep `target_language` required for new requests, preserve the existing default behavior for callers that omit it, and keep `verify_back_translation` defaulting to `false`.
- [ ] Run `git diff --check` and commit:

```powershell
git add docs/superpowers/specs/2026-09-10-configurable-translation-design.md
git commit -m "docs: clarify translation model compatibility"
```

## Task 2: Add model-discovery helpers using TDD

**Files:** `app.py`, `tests/test_chat_translate_helpers.py`

- [ ] Add failing tests for these exact contracts:

```python
def test_build_models_url_replaces_chat_completions_suffix():
    assert build_models_url("http://localhost:8045/v1/chat/completions") == "http://localhost:8045/v1/models"


def test_build_models_url_handles_trailing_slash():
    assert build_models_url("http://localhost:8045/v1/chat/completions/") == "http://localhost:8045/v1/models"


def test_normalize_models_response_returns_id_and_name():
    assert normalize_models_response({"data": [{"id": "gemini-3.8-flash-high"}]}) == [
        {"id": "gemini-3.8-flash-high", "name": "gemini-3.8-flash-high"}
    ]


def test_normalize_models_response_rejects_invalid_data():
    with pytest.raises(ValueError):
        normalize_models_response({"data": [{"name": "missing-id"}]})
```

- [ ] Run `pytest tests/test_chat_translate_helpers.py -q`; expect failure because the helpers do not exist.
- [ ] Implement `build_models_url()` by trimming `/`, replacing `/chat/completions` with `/models`, accepting a `/v1` base, and raising `ValueError` for unsupported URLs. Implement `normalize_models_response()` to require a non-empty `data` list and a non-empty string `id`, returning `{id, name}` objects.
- [ ] Run the focused helper tests and expect all to pass.
- [ ] Commit with `git add app.py tests/test_chat_translate_helpers.py; git commit -m "test: add model discovery helpers"`.

## Task 3: Implement and test `GET /models`

**Files:** `app.py`, `tests/test_chat_translate_endpoint.py`

- [ ] Add tests for missing API key (`401`), successful OpenAI-format normalization, malformed model data (`502`), and upstream `requests` failure (`502`). The success test must assert URL `/v1/models` and header `Authorization: Bearer test-key`.
- [ ] Run the focused endpoint tests; expect `404` before implementation.
- [ ] Define one `DEFAULT_ANTIGRAVITY_URL` constant and add:

```python
@app.get("/models")
def list_models(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Vui long nhap Key")
    try:
        models_url = build_models_url(os.getenv("ANTIGRAVITY_URL", DEFAULT_ANTIGRAVITY_URL))
        response = requests.get(
            models_url,
            headers={"Authorization": f"Bearer {x_api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        return {"models": normalize_models_response(response.json())}
    except (ValueError, requests.RequestException, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Không thể lấy danh sách model: {exc}")
```

- [ ] Run `pytest tests/test_chat_translate_endpoint.py tests/test_chat_translate_helpers.py -q`; expect all tests to pass.
- [ ] Commit with `git add app.py tests/test_chat_translate_endpoint.py; git commit -m "feat: discover translation models through backend"`.

## Task 4: Extend quick translation

**Files:** `app.py`, `tests/test_translate_endpoint.py`

- [ ] Create failing TestClient tests that mock `requests.post` and cover: selected model/verify flag forwarded; structured response `{result, source_language, back_translated_text}` returned; omitted model uses `gemini-3-flash-agent`; explicitly empty model returns `400`.
- [ ] Run `pytest tests/test_translate_endpoint.py -q`; expect failures before implementation.
- [ ] Extend `TranslateRequest` with `target_language: str | None = None`, `model: str | None = None`, and `verify_back_translation: bool = False`. Preserve the old Vietnamese/Chinese prompt when `target_language` is omitted; reject explicitly empty target/model values.
- [ ] Replace the quick prompt with a strict JSON prompt containing `result`, `source_language`, and `back_translated_text`. Require the last field to be empty unless verify is enabled, target is not Vietnamese, and the source is Vietnamese.
- [ ] Send `request.model or "gemini-3-flash-agent"` upstream, strip optional JSON markdown fences, parse/validate the response, and keep TinyDB history keyed by the primary result.
- [ ] Run `pytest tests/test_translate_endpoint.py tests/test_chat_translate_endpoint.py tests/test_chat_translate_helpers.py -q` and expect all to pass.
- [ ] Commit with `git add app.py tests/test_translate_endpoint.py; git commit -m "feat: add configurable quick translation verification"`.

## Task 5: Extend Chat Translate

**Files:** `app.py`, `tests/test_chat_translate_helpers.py`, `tests/test_chat_translate_endpoint.py`

- [ ] Add failing tests asserting `build_chat_translate_prompt(..., verify_back_translation=True)` mentions `back_translated_text` and Vietnamese conditions, and a request with `model="gemini-3.8-flash-high"` forwards that model and returns the back-translation field.
- [ ] Extend `ChatTranslateRequest` with `model: str | None = None` and `verify_back_translation: bool = False`. Reject explicit empty model values; use `gemini-3-flash` when omitted.
- [ ] Extend `build_chat_translate_prompt()` with `verify_back_translation` and strict JSON output rules. Use `request.model or "gemini-3-flash"` in the upstream payload.
- [ ] Preserve ID mapping; accept missing optional `back_translated_text` as `""`, but reject a non-string value. Keep existing `id` and `translated_text` validation.
- [ ] Run `pytest -q`; expect all tests to pass.
- [ ] Commit with `git add app.py tests/test_chat_translate_helpers.py tests/test_chat_translate_endpoint.py; git commit -m "feat: add chat model selection and back-translation"`.

## Task 6: Add shared frontend settings, discovery, and cache

**Files:** `index.html`

- [ ] Add a shared settings card with IDs `translationTargetLanguage`, `translationModel`, `refreshModelsBtn`, `verifyBackTranslation`, `modelStatus`, and `customTargetLanguage`. Keep only one source of truth for target language; synchronize/remove the old `chatTargetLanguage` control.
- [ ] Add `translationSettings` localStorage state with `{targetLanguage, customTargetLanguage, model, verifyBackTranslation}`. Implement `loadTranslationSettings()`, `saveTranslationSettings()`, `getSelectedTargetLanguage()`, and `getTranslationOptions()`, safely falling back on invalid JSON.
- [ ] Implement `loadModels()` to call `GET /models` with `x-api-key`, show loading/success/error status, populate the model dropdown, restore a cached model only if returned, and disable translation actions when discovery fails or returns no models. Add 500ms API-key debounce plus an immediate refresh button.
- [ ] On settings changes, save cache and retranslate an active outgoing preview. Keep API key storage behavior unchanged.
- [ ] Manually verify model loading, refresh/error state, reload restoration, and disabled translation controls in the browser.
- [ ] Commit with `git add index.html; git commit -m "feat: add shared translation settings and model cache"`.

## Task 7: Render inline back-translation in every flow

**Files:** `index.html`

- [ ] Update quick, incoming chat, outgoing preview, and outgoing commit payloads to include `target_language`, `model`, and `verify_back_translation` from `getTranslationOptions()`.
- [ ] Add `sourceLanguage` and `backTranslatedText` to quick state, chat messages, and outgoing preview. Render the order original → primary translation → green `Dịch ngược để verify` block only when the field is non-empty.
- [ ] Clear stale back-translation state on input clear, errors, and setting changes. Increment the existing preview request ID so stale responses are ignored.
- [ ] Manually verify: Vietnamese→English with verify on shows three levels; verify off shows two; Chinese→Vietnamese shows no verify line; all three UI flows use the same layout.
- [ ] Commit with `git add index.html; git commit -m "feat: render inline back-translation verification"`.

## Task 8: Final verification and AGY review

**Files:** none expected.

- [ ] Run `pytest -q`; expected result is zero failures.
- [ ] Run `git diff --check HEAD~7..HEAD`, inspect any pre-existing whitespace warnings without broad rewriting, then run `git diff HEAD~7..HEAD --stat` and `git status --short --branch`.
- [ ] Confirm only planned files changed and the working tree is clean.
- [ ] Run the user-approved read-only AGY review:

```powershell
agy --dangerously-skip-permissions --add-dir (Get-Location).Path --model gemini-3.8-flash-high --effort high --mode plan --print "Chỉ review diff và test result cho feature configurable translation. Không sửa file. Báo cáo các lỗi còn lại." --print-timeout 3m
```

- [ ] Address only concrete in-scope findings, then rerun `pytest -q` and `git status --short --branch`.
