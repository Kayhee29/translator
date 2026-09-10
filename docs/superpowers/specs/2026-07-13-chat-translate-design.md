# Chat Translate Design

**Date:** 2026-07-13

## Summary

Add a new `chat_translate` capability to the existing `translate` route. The feature should present a chat-style interface that lets users paste content for both conversation roles, translate each message with awareness of nearby conversation context, and display the translation directly under the original message.

This feature must not be hard-coded to Vietnamese and Chinese. Instead, the user selects a single `Translate to` target language for the current session. The system should use a reduced context window so translations remain meaningful without sending the entire conversation on every request.

## Goals

- Add a chat-like translation workflow alongside the current single-text translation flow.
- Support two input modes:
  - `Chat bubbles` as the default mode
  - `Bulk paste` as a fast-input mode
- Keep the original text visible and render the translated text below each message.
- Use nearby conversation context so translations reflect meaning, tone, and referents better than isolated sentence translation.
- Support a single session-level target language selected by the user.
- Optimize token usage by sending only the messages being translated plus a reduced context window.

## Non-Goals

- Full conversation memory summarization in the first version
- Per-message target language selection
- Persistent cross-session chat history management
- Real-time streaming translation while typing
- Automatic language locking to a fixed pair such as Vietnamese/Chinese only

## Current Project Context

The current codebase in this folder is a small FastAPI service centered in `app.py`. It already supports:

- Single-text translation via `/translate`
- Xianyu-oriented single and batch translation
- TinyDB-backed history and quick chat storage
- Product capture endpoints

There is no frontend code in this folder. Because the user explicitly wants the feature in the `translate` route, this design assumes one of two implementation realities:

1. The `translate` route UI lives in another codebase and this backend will expose the API needed by that UI.
2. If the UI is also added here later, new frontend files will need to be created in addition to backend changes.

The first implementation pass should keep the backend independent and well-defined so the UI can consume it cleanly.

## User Experience

### Primary Entry

Inside the `translate` route, add a new `Chat Translate` module next to the existing translation experience instead of replacing current behavior.

### Input Modes

#### 1. Chat Bubbles

This is the default mode.

Users can:

- add a new message bubble
- choose a role for each bubble
- paste original content into each bubble
- edit or delete bubbles
- translate all untranslated bubbles or selected bubbles

Recommended role labels:

- `Role A`
- `Role B`

Optional UI copy may map these to common marketplace roles such as buyer and seller, but the stored value should stay generic enough to support broader use.

#### 2. Bulk Paste

This mode is a helper for faster data entry.

Users can:

- paste large blocks of conversation text
- assign pasted content to `Role A` or `Role B`
- convert the pasted text into message bubbles

Default splitting rule:

- split on blank lines between paragraphs

This is the safest default for pasted chat logs because it avoids fragmenting messages line by line. Future iterations may offer an alternate `split by line` option, but that is out of scope for the first version unless the frontend already has a pattern for such options.

### Session Controls

The `Chat Translate` module should expose:

- `Translate to` language selector for the entire session
- mode switch between `Chat bubbles` and `Bulk paste`
- add message action
- translate action
- clear conversation action

### Message Presentation

Each bubble should show:

- role label
- original message
- translated message directly below it
- status indicator: `idle`, `translating`, `translated`, or `error`

If translation fails for a message, the original text remains untouched and the bubble shows an inline error state.

## Functional Requirements

### Translation Behavior

When translating messages:

- the system must preserve the original message text
- the system must return one translated result per requested message
- the system must use nearby messages as supporting context
- the system must translate only the requested messages, not the full conversation unless explicitly requested

The AI prompt should instruct the model to:

- treat the payload as a multi-turn conversation
- use nearby context to resolve pronouns, tone, omitted subjects, and implied references
- translate naturally into the selected target language
- avoid commentary, explanation, or formatting
- return structured output that maps cleanly to message IDs

### Reduced Context Window

To control token usage, the backend should not send the entire conversation every time.

Default rule for v1:

- for each translation request, include all target messages
- include up to 5 prior messages before the earliest target message
- include up to 2 following messages only if they already exist and if the implementation later supports re-translation workflows

For the first implementation, it is acceptable to include only prior context and omit following context.

If the user edits an already translated bubble and requests translation again:

- retranslate that bubble
- rebuild context from nearby messages based on its new position

### Target Language

The target language is selected once per session request and applies to all messages translated in that call.

Examples:

- Vietnamese
- English
- Chinese
- Japanese

The backend should accept free-text language names rather than a hard-coded enum so the UI remains flexible. Validation should still reject empty values.

### Bulk Paste Conversion

Bulk paste conversion should happen before translation.

The conversion layer should:

- accept a block of text
- assign it to a chosen role
- split by blank lines
- discard empty segments
- create message objects in the same structure used by `Chat bubbles`

This keeps the downstream translation path identical regardless of input mode.

## API Design

Add a new endpoint:

- `POST /chat_translate`

### Request Shape

```json
{
  "target_language": "Vietnamese",
  "messages": [
    {
      "id": "m1",
      "role": "role_a",
      "content": "你好，商品还在吗？"
    },
    {
      "id": "m2",
      "role": "role_b",
      "content": "Còn nhé, bạn cần thêm hình không?"
    }
  ],
  "message_ids_to_translate": ["m1", "m2"]
}
```

### Response Shape

```json
{
  "results": [
    {
      "id": "m1",
      "translated_text": "Xin chao, san pham nay con khong?",
      "source_language": "Chinese"
    },
    {
      "id": "m2",
      "translated_text": "The item is still available. Do you need more photos?",
      "source_language": "Vietnamese"
    }
  ]
}
```

Notes:

- `source_language` is optional but useful if the model or UI wants to show detection metadata.
- The response must preserve `id` mapping so the frontend can merge results into the correct bubbles.

## Backend Design

### New Data Models

Add Pydantic models for:

- session message item
- chat translate request
- chat translate response item

Recommended fields:

- `id: str`
- `role: str`
- `content: str`
- `target_language: str`
- `message_ids_to_translate: list[str]`

### Context Builder

Introduce a helper function dedicated to reduced-context extraction.

Responsibilities:

- find target message indexes from `message_ids_to_translate`
- gather nearby prior messages
- include the target messages themselves
- return a compact ordered list for prompt construction

This logic should be isolated from the HTTP route so it is easy to test without network calls.

### Prompt Builder

Introduce a helper that converts the reduced message window into a stable model prompt.

Responsibilities:

- describe translation objective
- state the target language
- provide role-tagged message context
- instruct the model to return strict JSON keyed by message ID

This should also be independently testable.

### Translation Client

Reuse the existing Antigravity-compatible chat completions endpoint pattern already used in `/translate` and related routes.

The implementation should:

- honor `x_api_key`
- reuse `ANTIGRAVITY_URL` environment fallback
- parse JSON response safely
- raise explicit HTTP errors when model output is invalid or missing expected fields

## Error Handling

The endpoint must reject:

- missing API key with `401`
- empty `target_language` with `400`
- empty message list with `400`
- unknown `message_ids_to_translate` with `400`
- messages with empty `id` or empty `content` with `400`
- invalid AI output with `500`

When one message fails because the model response is malformed for that item, the first version may fail the whole request rather than partially succeed. This keeps the implementation smaller and easier to reason about.

## Testing Strategy

Add focused unit tests for:

- reduced context selection
- bulk paste splitting logic
- prompt builder output structure
- request validation

Add endpoint tests for:

- successful translation of a short multi-role conversation
- retranslation of only selected message IDs
- invalid request shapes
- AI returning non-JSON or missing IDs

Mock outbound HTTP calls so tests do not depend on the live translation service.

## Open Assumptions

- The UI for the `translate` route is not present in this folder, so backend API work should be treated as the primary deliverable in this codebase.
- If a frontend implementation is later added here, it should consume the new backend contract rather than embedding translation logic in the browser.
- The first version will not persist `chat_translate` sessions in TinyDB unless a later requirement explicitly asks for session recovery.

## Rollout Recommendation

Implement in two layers:

1. Backend API and tests in this repository
2. Frontend `translate` route integration in the UI codebase that owns the current route

This keeps the current service maintainable and avoids mixing an unscoped frontend build into a backend-only folder.
