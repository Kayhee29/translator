# Directional Translation for Quick and Chat Modes

## Goal

Restore automatic reverse-direction translation for both quick translation and chat translation without changing the public request/response contract.

## User behavior

When a non-Vietnamese target language is selected, the system uses Vietnamese as the conversation counterpart language:

- Chat outgoing messages (`role_b`, “Tin nhắn của tôi”) translate Vietnamese into the selected target language.
- Chat incoming messages (`role_a`, “Tin nhắn đối phương”) translate the counterpart language into Vietnamese.
- Quick translation detects the input direction. Vietnamese input translates into the selected target language; input already in the selected target language translates into Vietnamese.
- Inputs in another language continue to translate into the selected target language.
- Back-translation verification is returned only when the detected source is Vietnamese and the primary translation target is not Vietnamese. The verification text is Vietnamese.

When Vietnamese is selected as the target, all primary translations target Vietnamese and back-translation remains empty.

## Backend design

Keep the existing `/translate` and `/chat_translate` schemas and response fields. Update the model instructions so direction is explicit and consistent:

- `/translate` receives the selected target and asks the model to detect the source and choose the primary target using the quick-mode rules.
- `/chat_translate` uses message roles to assign the primary target: `role_b` targets the selected language, while `role_a` targets Vietnamese. The prompt continues to include nearby context and requested message IDs.
- The existing structured JSON parser and plain-text fallback remain unchanged. Validation of result IDs, result strings, source language, and verification fields remains unchanged.

## Frontend design

Retain the current shared language/model/verify controls and payloads. Update explanatory text only where needed so users understand that chat direction depends on the composer role and quick mode auto-detects direction. Existing cached model and translation settings remain compatible.

## Error handling and compatibility

- Existing model discovery, API-key handling, cache behavior, SSE parsing, and upstream error handling are preserved.
- Existing callers that send `/translate` or `/chat_translate` continue to use the same fields.
- If the model cannot determine a source language, it follows the selected target as the safe fallback.
- Invalid structured responses continue to fail validation rather than being silently accepted.

## Testing

Add regression tests for:

1. Quick Vietnamese → selected language with optional Vietnamese verification.
2. Quick selected language → Vietnamese without verification text.
3. Chat outgoing Vietnamese → selected language with verification.
4. Chat incoming selected language → Vietnamese.
5. Existing JSON, text fallback, SSE, and validation behavior remains passing.

Run the focused endpoint tests, full test suite, Python compilation, and whitespace checks before deployment.
