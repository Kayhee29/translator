# Index Chat Screen UI Design

**Date:** 2026-07-13

## Summary

Revise `index.html` so the `Chat Translate` mode feels like a real chat screen instead of a free-form bubble builder.

The page should keep the existing `Dich nhanh` mode, but when the user switches to `Chat Translate`, the interface should become:

- a conversation area that renders left/right chat bubbles
- one input box for the other person's message
- one input box for the user's own message
- actions that append messages into the conversation and translate the user's outgoing message using the full visible conversation as context

This is a simpler and more natural workflow than asking the user to manually create arbitrary message bubbles.

## Goals

- Keep the current quick-translate screen available through the existing mode switch.
- Make `Chat Translate` look and feel like a real chat app conversation.
- Replace the free-form bubble-editor concept with a two-composer workflow.
- Use the existing `/chat_translate` endpoint without requiring backend changes.
- Preserve the same visual language as the current `index.html`.

## Non-Goals

- A general-purpose multi-role conversation editor
- Bulk paste as a primary workflow in the first UI version
- Message persistence between page reloads
- Live streaming translation
- Multi-user accounts or sessions

## Current Code Mismatch

The current `Chat Translate` implementation in `index.html` is not aligned with the intended use case because it:

- lets the user add arbitrary message bubbles
- requires per-bubble role selection
- includes bulk-paste tooling as a core UI feature

That makes the feature feel like a manual conversation editor rather than a realistic chat screen.

The revised design must instead model a simple conversation with two clear directions:

- incoming messages from the other person
- outgoing messages from the user

## User Experience

### Mode Switch

Keep the existing horizontal mode switch:

- `Dich nhanh`
- `Chat Translate`

Switching to `Chat Translate` should reveal a dedicated chat workspace and hide the quick-translate panel.

### Chat Workspace

The chat workspace should include:

1. Conversation header
2. Scrollable conversation area
3. Two fixed input sections at the bottom

### Conversation Area

This should visually resemble a messaging app:

- incoming messages appear on the left
- outgoing messages appear on the right
- messages are grouped in a single scrollable timeline
- each bubble shows original text and, where applicable, translated text

### Two Input Boxes

#### 1. Other Person Input

Label example:

- `Tin nhan doi phuong`

Purpose:

- the user pastes or types the message they received
- pressing `Them vao hoi thoai` creates a left-side bubble in the timeline

This message may also be translated into the selected target language for readability, but that is secondary to its main role as context for the user's next message.

#### 2. My Message Input

Label example:

- `Tin nhan cua toi`

Purpose:

- the user writes what they want to say
- pressing `Dich va them vao hoi thoai` sends the current conversation plus this outgoing draft to `/chat_translate`
- the UI then adds a right-side bubble containing the translated message

Recommended display treatment:

- show the user's original draft in smaller or lighter text
- show the translated result more prominently beneath it

This matches the idea that the translation is the sendable message, while the original is supporting context for the user.

## Message Model

The frontend should maintain a lightweight message structure:

```javascript
{
  id: "m1",
  role: "role_a" | "role_b",
  content: "original text",
  translatedText: "translated text",
  direction: "incoming" | "outgoing",
  status: "idle" | "translating" | "translated" | "error",
  error: ""
}
```

Suggested mapping:

- `incoming` messages use `role_a`
- `outgoing` messages use `role_b`

This keeps the frontend readable while still matching backend expectations.

## API Usage

Use the existing `POST /chat_translate` endpoint.

### Incoming Message Flow

When the user submits the other person's message:

- append the original message to the conversation as an incoming bubble
- optionally translate it with the full conversation context if needed later

For the first version, the incoming message does not need immediate translation unless the user explicitly triggers it as part of a broader conversation translation pass.

### Outgoing Message Flow

When the user submits their own draft:

- create a temporary outgoing message entry
- send the full conversation, including that new outgoing draft, to `/chat_translate`
- request translation for the contiguous visible conversation block
- apply the translated result back to the outgoing message bubble

To stay compatible with current backend validation, the simplest rule is:

- always submit the full current visible conversation
- always request translation for all message IDs in that visible conversation

This avoids non-contiguous edge cases and keeps frontend logic small.

## Visual Design Direction

The new chat UI should stay visually consistent with the existing page:

- same rounded white cards
- same light-gray page background
- same blue accent used by quick translate
- same soft shadows and border treatments

The chat timeline should look more conversational than form-like.

### Bubble Styling

Incoming bubbles:

- left aligned
- light gray or very pale neutral background

Outgoing bubbles:

- right aligned
- soft blue background or stronger blue treatment consistent with the site

Translated text should be clearly readable and visually emphasized more than helper metadata.

## Layout

### Desktop

- left main area: active mode workspace
- right sidebar:
  - quick mode shows history
  - chat mode shows a small guide or shortcuts card

### Mobile

- chat timeline stays scrollable
- both input boxes stack vertically
- action buttons remain large enough to tap comfortably

## Error Handling

Chat mode should handle:

- missing API key
- empty incoming input when trying to add it
- empty outgoing input when trying to translate it
- backend validation errors
- translation failures

Errors should appear inline near chat controls, not through disruptive modal alerts.

## Scope Boundary

The first revision should remove or de-emphasize the following from chat mode:

- add-arbitrary-bubble controls
- per-bubble role selector
- bulk-paste as a central interaction pattern

If bulk paste remains in code for reuse, it should not be the main path exposed to users in the UI.

## Testing Strategy

Manual verification should cover:

- switch between `Dich nhanh` and `Chat Translate`
- add an incoming message to the timeline
- translate an outgoing message into the selected target language
- preserve the visible conversation while switching modes
- keep quick mode unchanged
- confirm mobile usability
