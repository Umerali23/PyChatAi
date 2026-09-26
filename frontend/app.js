/**
 * PyChat AI - Milestone 4 frontend logic
 *
 * Talks to the FastAPI backend on the same origin.
 * Conversation state lives in memory for now; persistence arrives in M8.
 */

(() => {
    "use strict";

    // ---------- DOM refs ----------
    const $ = (id) => document.getElementById(id);

    const messagesEl        = $("messages");
    const emptyStateEl      = $("empty-state");
    const composerForm      = $("composer-form");
    const messageInput      = $("message-input");
    const sendBtn           = $("send-btn");
    const newChatBtn        = $("new-chat-btn");
    const conversationListEl= $("conversation-list");
    const chatTitleEl       = $("chat-title");
    const chatModelEl       = $("chat-model");
    const statusDot         = $("status-dot");
    const statusText        = $("status-text");
    const menuBtn           = $("menu-btn");
    const sidebarEl         = $("sidebar");
    const sidebarOverlay    = $("sidebar-overlay");
    const suggestionsEl     = $("suggestions");

    const API = { chat: "/api/chat", health: "/health" };

    // ---------- State ----------
    const state = {
        conversations: [],   // [{ id, title, createdAt, messages: [{role, content}] }]
        activeId: null,
        sending: false,
    };

    // ---------- Helpers ----------

    const uid = () =>
        Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

    const formatTime = (date) =>
        date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    function deriveTitle(text) {
        const clean = text.replace(/\s+/g, " ").trim();
        return clean.length > 42 ? clean.slice(0, 42) + "…" : clean;
    }

    const getActiveConversation = () =>
        state.conversations.find((c) => c.id === state.activeId) || null;

    // ---------- Health check ----------

    async function checkHealth() {
        try {
            const res = await fetch(API.health);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            chatModelEl.textContent = data.model || "unknown";
            if (data.ollama_running) {
                statusDot.className = "status-dot ok";
                statusText.textContent = "Connected";
            } else {
                statusDot.className = "status-dot warn";
                statusText.textContent = "Ollama offline";
            }
        } catch (_) {
            statusDot.className = "status-dot error";
            statusText.textContent = "Server unreachable";
        }
    }

    // ---------- Rendering ----------

    function renderEmptyState() {
        const conv = getActiveConversation();
        const hasMessages = Boolean(conv && conv.messages.length > 0);
        emptyStateEl.classList.toggle("hidden", hasMessages);
    }

    function clearMessages() {
        // replaceChildren() with no args is the safe, modern way to empty
        // a node — no innerHTML involved.
        messagesEl.replaceChildren();
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        });
    }

    function appendMessage(role, content, { error = false } = {}) {
        const wrapper = document.createElement("div");
        wrapper.className = `message ${role}${error ? " error" : ""}`;

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = role === "user" ? "You" : error ? "!" : "Py";

        const body = document.createElement("div");
        body.className = "message-body";

        const contentEl = document.createElement("div");
        contentEl.className = "message-content";
        // textContent escapes automatically — important since AI output
        // is untrusted. Markdown rendering arrives safely in M7.
        contentEl.textContent = content;

        const meta = document.createElement("div");
        meta.className = "message-meta";
        meta.textContent = formatTime(new Date());

        body.append(contentEl, meta);
        wrapper.append(avatar, body);
        messagesEl.appendChild(wrapper);
        scrollToBottom();
        return wrapper;
    }

    function appendTyping() {
        const wrapper = document.createElement("div");
        wrapper.className = "message assistant";
        wrapper.dataset.typing = "true";

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = "Py";

        const body = document.createElement("div");
        body.className = "message-body";

        const indicator = document.createElement("div");
        indicator.className = "typing";
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement("span");
            dot.className = "typing-dot";
            indicator.appendChild(dot);
        }

        body.appendChild(indicator);
        wrapper.append(avatar, body);
        messagesEl.appendChild(wrapper);
        scrollToBottom();
        return wrapper;
    }

    function removeTyping() {
        messagesEl.querySelector('[data-typing="true"]')?.remove();
    }

    function renderConversationList() {
        conversationListEl.replaceChildren();
        const sorted = [...state.conversations].sort(
            (a, b) => b.createdAt - a.createdAt
        );
        for (const conv of sorted) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className =
                "conversation-item" +
                (conv.id === state.activeId ? " active" : "");
            btn.textContent = conv.title;
            btn.title = conv.title;
            btn.addEventListener("click", () => selectConversation(conv.id));
            conversationListEl.appendChild(btn);
        }
    }

    function renderActiveConversation() {
        const conv = getActiveConversation();
        clearMessages();

        if (!conv) {
            chatTitleEl.textContent = "New conversation";
            renderEmptyState();
            return;
        }

        chatTitleEl.textContent = conv.title;
        for (const msg of conv.messages) {
            appendMessage(msg.role, msg.content);
        }
        renderEmptyState();
    }

    // ---------- Conversation management ----------

    function createConversation() {
        const conv = {
            id: uid(),
            title: "New conversation",
            createdAt: Date.now(),
            messages: [],
        };
        state.conversations.push(conv);
        state.activeId = conv.id;
        return conv;
    }

    function selectConversation(id) {
        state.activeId = id;
        renderConversationList();
        renderActiveConversation();
        closeSidebarOnMobile();
    }

    function startNewChat() {
        const existingEmpty = state.conversations.find(
            (c) => c.messages.length === 0
        );
        if (existingEmpty) {
            state.activeId = existingEmpty.id;
        } else {
            createConversation();
        }
        renderConversationList();
        renderActiveConversation();
        messageInput.focus();
        closeSidebarOnMobile();
    }

    // ---------- Sending ----------

    function updateSendButton() {
        sendBtn.disabled =
            state.sending || messageInput.value.trim().length === 0;
    }

    function setSending(value) {
        state.sending = value;
        updateSendButton();
    }

    function buildHistoryPayload(messages) {
        // Send the last up-to-20 turns. Backend also caps.
        return messages.slice(-20).map((m) => ({
            role: m.role,
            content: m.content,
        }));
    }

    async function sendMessage(rawText) {
        if (state.sending) return;
        const text = (rawText ?? "").trim();
        if (!text) return;

        let conv = getActiveConversation();
        if (!conv) conv = createConversation();

        // Snapshot history *before* adding the current user message.
        const history = buildHistoryPayload(conv.messages);
        conv.messages.push({ role: "user", content: text });

        if (conv.messages.length === 1) {
            conv.title = deriveTitle(text);
            chatTitleEl.textContent = conv.title;
            renderConversationList();
        }

        // Reset composer
        messageInput.value = "";
        autoGrowInput();
        updateSendButton();

        renderEmptyState();
        appendMessage("user", text);
        appendTyping();
        setSending(true);

        try {
            const res = await fetch(API.chat, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, history }),
            });

            let data = null;
            try { data = await res.json(); } catch (_) { /* non-JSON body */ }

            removeTyping();

            if (!res.ok) {
                const detail =
                    (data && (data.detail || data.message)) ||
                    `Request failed with status ${res.status}`;
                const text =
                    typeof detail === "string"
                        ? detail
                        : JSON.stringify(detail);
                appendMessage("assistant", text, { error: true });
                return;
            }

            const reply = (data && data.reply) || "(empty response)";
            conv.messages.push({ role: "assistant", content: reply });
            appendMessage("assistant", reply);
        } catch (_) {
            removeTyping();
            appendMessage(
                "assistant",
                "Could not reach the server. Is it still running?",
                { error: true }
            );
        } finally {
            setSending(false);
            messageInput.focus();
        }
    }

    // ---------- Composer ----------

    function autoGrowInput() {
        messageInput.style.height = "auto";
        const maxHeight = 200;
        messageInput.style.height =
            Math.min(messageInput.scrollHeight, maxHeight) + "px";
    }

    function handleSubmit(event) {
        event.preventDefault();
        sendMessage(messageInput.value);
    }

    function handleKeydown(event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage(messageInput.value);
        }
    }

    function handleInput() {
        autoGrowInput();
        updateSendButton();
    }

    // ---------- Sidebar (mobile) ----------

    function openSidebar() {
        sidebarEl.classList.add("open");
        sidebarOverlay.classList.add("visible");
    }
    function closeSidebar() {
        sidebarEl.classList.remove("open");
        sidebarOverlay.classList.remove("visible");
    }
    function closeSidebarOnMobile() {
        if (window.innerWidth <= 768) closeSidebar();
    }

    // ---------- Wiring ----------

    function bindEvents() {
        composerForm.addEventListener("submit", handleSubmit);
        messageInput.addEventListener("keydown", handleKeydown);
        messageInput.addEventListener("input", handleInput);

        newChatBtn.addEventListener("click", startNewChat);

        menuBtn.addEventListener("click", openSidebar);
        sidebarOverlay.addEventListener("click", closeSidebar);

        suggestionsEl.addEventListener("click", (event) => {
            const btn = event.target.closest(".suggestion");
            if (!btn) return;
            const prompt = btn.dataset.prompt || "";
            sendMessage(prompt);
        });
    }

    // ---------- Init ----------

    function init() {
        bindEvents();
        createConversation();
        renderConversationList();
        renderActiveConversation();
        updateSendButton();
        messageInput.focus();
        checkHealth();
        setInterval(checkHealth, 15000);
    }

    document.addEventListener("DOMContentLoaded", init);
})();