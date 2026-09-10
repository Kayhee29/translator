# Configurable Translation and Back-Translation Verification

## Goal

Upgrade the translation experience so users can choose the target language and the model supplied by the connected OpenAI-compatible endpoint. When enabled, Vietnamese-to-other-language translations also return a Vietnamese back-translation so the user can verify meaning. The feature applies to both Dịch nhanh and Chat Translate.

## Decisions

- Use the existing backend as the only browser-facing integration point.
- Discover models from the connected endpoint instead of maintaining a static model list.
- Store the selected target language, model, and verification preference in browser `localStorage`.
- Remember the verification preference across sessions.
- If model discovery fails, show the connection error and disable translation until the user retries successfully.
- Use the inline layout: original text, primary translation, then back-translation in the same result/message block.
- Back-translation is requested only when the option is enabled, the target language is not Vietnamese, and the model identifies the source as Vietnamese. Otherwise the response contains an empty back-translation field.

## User experience

Add a shared translation settings area usable by both modes:

- Target language selector with the current supported presets and a custom language option.
- Model selector populated from `GET /models`.
- Refresh models action.
- “Dịch ngược để verify” checkbox whose state is persisted.
- Connection/model loading/error status visible near the controls.

On startup, the frontend calls `/models` with the API key. A successful response populates the model selector and restores the cached model when it is still available. The target language, selected model, and verify state are restored from `localStorage`. Changing any setting updates the cache and causes an active outgoing chat preview to retranslate.

For each translated result, render:

1. Original text.
2. Primary translation.
3. A visually distinct “Dịch ngược để verify” line when `back_translated_text` is non-empty.

If model discovery fails, display the backend error, leave the previous cached settings visible where possible, and disable translation actions. The refresh action retries discovery. The API key is never stored in the settings cache beyond the existing behavior.

## Backend API

### `GET /models`

Requires the existing `x-api-key` header. The backend derives the models URL from `ANTIGRAVITY_URL` by replacing the `/chat/completions` suffix with `/models`, calls it with the bearer API key, and normalizes the OpenAI-compatible response:

```json
{
  "data": [
    { "id": "gemini-3-flash" }
  ]
}
```

The response to the browser is:

```json
{
  "models": [
    { "id": "gemini-3-flash", "name": "gemini-3-flash" }
  ]
}
```

Missing API keys, invalid upstream responses, network failures, and empty model lists return explicit HTTP errors. The backend does not invent a fallback model.

### `POST /translate`

Extend the request with:

```json
{
  "target_language": "English",
  "model": "gemini-3-flash",
  "verify_back_translation": true
}
```

The browser UI requires a successfully discovered model before enabling translation. For backward compatibility, API callers that omit `model` use the existing endpoint-specific default. A supplied empty `model` is rejected with `400`. `target_language` is required for new requests, while callers that omit it preserve the existing default behavior, and `verify_back_translation` defaults to `false`. The response keeps `result` and may include:

```json
{
  "result": "Hello",
  "source_language": "Vietnamese",
  "back_translated_text": "Xin chào"
}
```

### `POST /chat_translate`

Add the same `model` and `verify_back_translation` fields to the request. Each result keeps its current fields and may add `back_translated_text`:

```json
{
  "id": "m1",
  "translated_text": "Hello",
  "source_language": "Vietnamese",
  "back_translated_text": "Xin chào"
}
```

The request model is passed to the upstream chat-completions payload. The prompt requires strict JSON, preserves message IDs, and asks the model to detect source language and return a back-translation only under the conditions above.

## Frontend data flow

1. API key changes trigger model discovery with a short debounce and a manual refresh remains available.
2. `/models` success updates the model dropdown and enables translation actions.
3. Translation payloads include the selected target language, model, and verify flag for both quick and chat flows.
4. Quick mode renders primary and back-translations in the result panel.
5. Chat mode renders the same three-level inline block for incoming messages and outgoing previews/messages.
6. A target language or model change clears stale output states and re-runs the active outgoing preview when applicable.

## Error handling

- Return `401` when `x-api-key` is missing.
- Return `400` for empty target language or supplied empty model.
- Return `502` for upstream model-discovery failures or malformed upstream model data.
- Return `500` for malformed translation JSON or missing required translation fields.
- Frontend shows actionable Vietnamese error text and keeps the refresh action available.

## Testing

Backend tests will cover:

- `/models` authentication, successful normalization, malformed response, and upstream failure.
- Translation requests forwarding the selected model and verify flag.
- Prompt instructions and response parsing for back-translation.
- Existing request behavior when the new fields are omitted.
- Chat translation result mapping with and without back-translation.

Frontend verification will cover the settings controls, localStorage restore/update, model loading/error states, payload fields, and inline rendering using the browser UI.

## Scope boundaries

- No user accounts or server-side preference persistence.
- No static guarantee that every endpoint implements `/models`; unsupported endpoints are surfaced as an error per the chosen behavior.
- No separate translation provider integration.
- No automatic retry loop beyond the explicit refresh action.
