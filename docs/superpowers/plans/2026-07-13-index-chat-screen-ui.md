# Index Chat Screen UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Rework `Chat Translate` in `index.html` into a real chat-style screen with two fixed input boxes: one for incoming messages and one for the user's outgoing draft.

**Architecture:** Keep `index.html` as a single-page Tailwind + vanilla JavaScript UI. Preserve the existing `Dich nhanh` workflow, but replace the current free-form chat bubble editor with a chat timeline, two fixed composer areas, and simple message actions that call `/chat_translate`.

**Tech Stack:** HTML, Tailwind CSS CDN, vanilla JavaScript, existing FastAPI endpoints

---

## File Structure

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\index.html`

No new frontend files are required. Replace and simplify the current chat-mode UI inside `index.html`.

### Task 1: Remove Free-Form Bubble Builder Structure

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\index.html`

- [x] **Step 1: Remove add-bubble oriented controls**

Delete or replace the current chat header controls that are centered on:

- `Them bubble`
- per-bubble manual editing workflow
- bubble role management as a primary interaction

The remaining header controls should focus on:

- target language
- clear conversation

- [x] **Step 2: Remove the current free-form message editor area**

Delete the old bubble-builder rendering contract and replace it with a timeline container:

```html
<div id="chatTimeline" class="space-y-3 max-h-[48vh] overflow-y-auto custom-scrollbar p-1"></div>
```

- [x] **Step 3: Remove bulk paste from the main UI path**

Delete the visible bulk-paste block from chat mode for now, or hide it behind a secondary detail section that is not prominent.

Preferred first pass:

- remove it from the active layout entirely

- [x] **Step 4: Add a conversation summary header**

Insert a compact chat header:

```html
<div class="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
  <div>
    <div class="text-sm font-bold text-gray-700">Chat Translate</div>
    <div class="text-xs text-gray-400">Mo phong man hinh chat de dich theo ngu canh.</div>
  </div>
  <div class="flex items-center gap-2">
    <span class="text-xs font-bold text-gray-400">Target</span>
    <select id="chatTargetLanguage" class="rounded-xl border px-3 py-2 text-sm outline-none bg-gray-50 font-semibold text-gray-700">
      <option>Vietnamese</option>
      <option>English</option>
      <option>Chinese</option>
      <option>Japanese</option>
      <option>Korean</option>
    </select>
    <button id="clearChatBtn" class="px-3 py-2 rounded-xl bg-red-50 text-red-600 text-xs font-bold">Xoa hoi thoai</button>
  </div>
</div>
```

- [x] **Step 5: Confirm the new chat container renders cleanly**

Open `index.html` and verify:

- quick mode still appears unchanged
- chat mode shows a clean empty chat container
- no leftover add-bubble or bulk-paste UI remains in the main path

### Task 2: Add Real Chat Timeline Markup

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\index.html`

- [x] **Step 1: Define the new message shape in frontend state**

Replace the old free-form message assumptions with:

```javascript
function createChatMessage({ direction, content, translatedText = "", status = "idle", error = "" }) {
  const id = `m${appState.chat.nextMessageId++}`;
  return {
    id,
    role: direction === "incoming" ? "role_a" : "role_b",
    direction,
    content,
    translatedText,
    status,
    error,
  };
}
```

- [x] **Step 2: Replace `renderChatMessages()` with a timeline renderer**

Use a renderer shaped like:

```javascript
function renderChatTimeline() {
  const container = document.getElementById("chatTimeline");

  if (!appState.chat.messages.length) {
    container.innerHTML = `
      <div class="rounded-2xl border border-dashed border-gray-200 p-6 text-sm text-gray-400 text-center">
        Chua co hoi thoai nao. Them tin nhan doi phuong hoac nhap cau tra loi cua ban o ben duoi.
      </div>
    `;
    return;
  }

  container.innerHTML = appState.chat.messages.map((message) => {
    const isIncoming = message.direction === "incoming";
    return `
      <div class="flex ${isIncoming ? "justify-start" : "justify-end"}">
        <div class="max-w-[85%] rounded-3xl px-4 py-3 shadow-sm border ${isIncoming ? "bg-white border-gray-200 text-gray-700" : "bg-blue-600 border-blue-500 text-white"}">
          <div class="text-sm whitespace-pre-wrap">${message.content}</div>
          ${message.translatedText ? `
            <div class="mt-2 pt-2 border-t ${isIncoming ? "border-gray-100 text-gray-600" : "border-white/20 text-white/90"}">
              <div class="text-[10px] uppercase tracking-wide ${isIncoming ? "text-gray-400" : "text-white/60"}">Ban dich</div>
              <div class="text-sm font-semibold whitespace-pre-wrap">${message.translatedText}</div>
            </div>
          ` : ""}
          ${!isIncoming && message.translatedText ? `
            <div class="mt-2 text-xs ${isIncoming ? "text-gray-400" : "text-white/70"}">Ban goc: ${message.content}</div>
          ` : ""}
          ${message.error ? `<div class="mt-2 text-xs text-red-200">${message.error}</div>` : ""}
        </div>
      </div>
    `;
  }).join("");
}
```

- [x] **Step 3: Auto-scroll timeline after updates**

After rendering, add:

```javascript
container.scrollTop = container.scrollHeight;
```

- [x] **Step 4: Replace empty-state copy**

Ensure the empty state talks about:

- incoming message
- outgoing draft

not about adding bubbles.

- [x] **Step 5: Verify chat visuals manually**

Check that:

- incoming messages sit on the left
- outgoing messages sit on the right
- the layout feels like a real chat screen

### Task 3: Add Two Fixed Input Boxes

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\index.html`

- [x] **Step 1: Add incoming-message composer**

Insert below the timeline:

```html
<div class="rounded-2xl border bg-gray-50 p-4 space-y-3">
  <div class="text-sm font-bold text-gray-700">Tin nhan doi phuong</div>
  <textarea id="incomingMessageInput" class="w-full min-h-[110px] rounded-2xl border bg-white p-4 text-sm outline-none resize-y" placeholder="Dan tin nhan nguoi dang chat voi ban..."></textarea>
  <div class="flex justify-end">
    <button id="appendIncomingBtn" class="px-4 py-2.5 rounded-xl bg-gray-900 text-white text-sm font-semibold">Them vao hoi thoai</button>
  </div>
</div>
```

- [x] **Step 2: Add outgoing-message composer**

Insert below the incoming composer:

```html
<div class="rounded-2xl border bg-blue-50 p-4 space-y-3">
  <div class="text-sm font-bold text-blue-900">Tin nhan cua toi</div>
  <textarea id="outgoingMessageInput" class="w-full min-h-[110px] rounded-2xl border bg-white p-4 text-sm outline-none resize-y" placeholder="Nhap dieu ban muon noi..."></textarea>
  <div class="flex justify-end">
    <button id="translateOutgoingBtn" class="px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold">Dich va them vao hoi thoai</button>
  </div>
</div>
```

- [x] **Step 3: Remove per-message editing interactions**

Delete old event delegation for:

- per-bubble role change
- per-bubble delete
- per-bubble textarea editing

This interaction model is no longer the primary design.

- [x] **Step 4: Keep page-level chat error area**

Retain a top-level chat error container for request failures.

- [x] **Step 5: Verify the two-composer layout manually**

Check:

- incoming composer reads as “message from them”
- outgoing composer reads as “message from me”
- buttons are obvious and not overcrowded

### Task 4: Wire Conversation Actions

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\index.html`

- [x] **Step 1: Add incoming append action**

Implement:

```javascript
document.getElementById("appendIncomingBtn").addEventListener("click", () => {
  const input = document.getElementById("incomingMessageInput");
  const content = input.value.trim();
  if (!content) {
    setChatError("Chua co tin nhan doi phuong.");
    return;
  }

  setChatError("");
  appState.chat.messages.push(
    createChatMessage({
      direction: "incoming",
      content,
    })
  );
  input.value = "";
  renderChatTimeline();
});
```

- [x] **Step 2: Build chat payload from the full visible conversation**

Implement:

```javascript
function getChatPayloadWithOutgoingDraft(outgoingContent) {
  const baseMessages = appState.chat.messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
  }));

  const outgoingDraft = createChatMessage({
    direction: "outgoing",
    content: outgoingContent,
    status: "translating",
  });

  return {
    draftMessage: outgoingDraft,
    payload: {
      target_language: document.getElementById("chatTargetLanguage").value,
      messages: [
        ...baseMessages,
        {
          id: outgoingDraft.id,
          role: outgoingDraft.role,
          content: outgoingDraft.content,
        },
      ],
      message_ids_to_translate: [
        ...baseMessages.map((message) => message.id),
        outgoingDraft.id,
      ],
    },
  };
}
```

- [x] **Step 3: Add translate-outgoing action**

Implement:

```javascript
document.getElementById("translateOutgoingBtn").addEventListener("click", async () => {
  const key = document.getElementById("apiKey").value.trim();
  const outgoingInput = document.getElementById("outgoingMessageInput");
  const outgoingContent = outgoingInput.value.trim();

  if (!key) {
    setChatError("Vui long nhap API key.");
    return;
  }

  if (!outgoingContent) {
    setChatError("Chua co tin nhan cua ban de dich.");
    return;
  }

  setChatError("");
  const { draftMessage, payload } = getChatPayloadWithOutgoingDraft(outgoingContent);
  appState.chat.messages.push(draftMessage);
  renderChatTimeline();

  try {
    const response = await fetch(basePath + "chat_translate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": key,
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Khong the dich tin nhan.");
    }

    const translated = (data.results || []).find((item) => item.id === draftMessage.id);
    if (!translated) {
      throw new Error("Khong tim thay ban dich cho tin nhan cua ban.");
    }

    const target = appState.chat.messages.find((message) => message.id === draftMessage.id);
    if (target) {
      target.translatedText = translated.translated_text || "";
      target.status = "translated";
      target.error = "";
    }

    outgoingInput.value = "";
  } catch (error) {
    const target = appState.chat.messages.find((message) => message.id === draftMessage.id);
    if (target) {
      target.status = "error";
      target.error = error.message;
    }
    setChatError(error.message);
  }

  renderChatTimeline();
});
```

- [x] **Step 4: Keep clear-conversation action simple**

Implement:

```javascript
document.getElementById("clearChatBtn").addEventListener("click", () => {
  appState.chat.messages = [];
  setChatError("");
  document.getElementById("incomingMessageInput").value = "";
  document.getElementById("outgoingMessageInput").value = "";
  renderChatTimeline();
});
```

- [x] **Step 5: Verify real usage flow manually**

Test this flow:

1. Add one incoming message
2. Type one outgoing draft
3. Translate it
4. Confirm outgoing bubble appears on the right with translated text

### Task 5: Preserve Existing Quick Mode and Polish

**Files:**
- Modify: `C:\Users\Kayhee29\Desktop\docker\translate\index.html`

- [x] **Step 1: Keep quick mode unchanged**

Verify no regressions in:

- textarea translation
- output rendering
- history loading
- clipboard helpers

- [x] **Step 2: Keep mode switching stateful**

Ensure:

- switching to quick mode does not erase chat conversation
- switching back to chat restores the timeline

- [x] **Step 3: Update chat sidebar guidance**

Replace old bubble-editor instructions with:

- paste their message into the first box
- type your reply into the second box
- translate your message into the selected target language

- [x] **Step 4: Check mobile usability**

Verify:

- timeline scrolls properly
- both textareas are usable on narrow screens
- buttons remain easy to tap

- [x] **Step 5: Final smoke test**

Verify:

1. Quick mode still works
2. Chat mode feels like a chat screen
3. Incoming messages append left
4. Outgoing translated messages append right
5. State survives mode switching
