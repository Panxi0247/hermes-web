import { useState, useRef } from "react";
import type { SetStateAction } from "react";
import "./App.css";
import Chat from "./components/Chat";
import ChatHistory from "./components/ChatHistory";
import Schedule from "./components/Schedule";
import Settings from "./components/Settings";
import type { Conversation, Message } from "./types";
import {
  getWelcomeMessages,
  loadConversations,
  saveConversations,
  upsertConversation,
} from "./storage/conversations";

// page: 頁面導航（對應左側導覽列）
type Page = "schedule" | "chat" | "settings" | "history";

export default function App() {
  const [page, setPage] = useState<Page>("schedule");
  const [wsConnected, setWsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<Message[]>(getWelcomeMessages);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const conversationIdRef = useRef<string | null>(null);

  const persistMessages = (messages: Message[]) => {
    if (messages.length <= 1) return;

    setConversations((previous) => {
      const result = upsertConversation(previous, messages, conversationIdRef.current);
      saveConversations(result.conversations);

      if (!conversationIdRef.current) {
        conversationIdRef.current = result.conversationId;
        setConversationId(result.conversationId);
      }

      return result.conversations;
    });
  };

  const handleMessagesChange = (nextMessages: SetStateAction<Message[]>) => {
    setChatMessages((previous) => {
      const resolvedMessages =
        typeof nextMessages === "function" ? nextMessages(previous) : nextMessages;
      queueMicrotask(() => persistMessages(resolvedMessages));
      return resolvedMessages;
    });
  };

  const handleShowError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  const handleLoadConversation = (conversation: Conversation) => {
    conversationIdRef.current = conversation.id;
    setConversationId(conversation.id);
    setChatMessages(conversation.messages);
    setPage("chat");
  };

  const handleNewConversation = () => {
    conversationIdRef.current = null;
    setConversationId(null);
    setChatMessages(getWelcomeMessages());
    setPage("chat");
  };

  const handleDeleteConversation = (id: string) => {
    setConversations((previous) => {
      const next = previous.filter((conversation) => conversation.id !== id);
      saveConversations(next);
      return next;
    });

    if (conversationId === id) {
      conversationIdRef.current = null;
      setConversationId(null);
      setChatMessages(getWelcomeMessages());
    }
  };

  return (
    <div className="app">
      {/* 左側邊欄 Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-top">
          {/* Logo */}
          <h1 className="logo">
            Hermes<span className="logo-dot">.</span>
          </h1>

          {/* 導覽列 Nav */}
          <nav className="nav-list">
            <button
              className={`nav-item ${page === "schedule" ? "active" : ""}`}
              onClick={() => setPage("schedule")}
            >
              <span className="nav-icon">S</span>
              <span>Schedule</span>
            </button>
            <button
              className={`nav-item ${page === "chat" ? "active" : ""}`}
              onClick={() => setPage("chat")}
            >
              <span className="nav-icon">C</span>
              <span>Chat</span>
            </button>
            <button
              className={`nav-item ${page === "settings" ? "active" : ""}`}
              onClick={() => setPage("settings")}
            >
              <span className="nav-icon">⚙</span>
              <span>Settings</span>
            </button>
            <button
              className={`nav-item ${page === "history" ? "active" : ""}`}
              onClick={() => setPage("history")}
            >
              <span className="nav-icon">H</span>
              <span>History</span>
            </button>
          </nav>
        </div>

        {/* 連線狀態 — 統一看 WebSocket 連線 */}
        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${wsConnected ? "ok" : "error"}`} />
            <span className="status-text">
              {wsConnected ? "已連接" : "未連接"}
            </span>
          </div>
        </div>
      </aside>

      {/* 錯誤橫幅 */}
      {error && <div className="error-banner">{error}</div>}

      {/* 主內容區 Main Content */}
      <main className="main">
        {page === "schedule" && <Schedule />}
        {page === "chat" && (
          <Chat
            onError={handleShowError}
            messages={chatMessages}
            onMessagesChange={handleMessagesChange}
            onWsConnectedChange={setWsConnected}
          />
        )}
        {page === "settings" && <Settings />}
        {page === "history" && (
          <ChatHistory
            conversations={conversations}
            onLoadConversation={handleLoadConversation}
            onNewConversation={handleNewConversation}
            onDeleteConversation={handleDeleteConversation}
          />
        )}
      </main>
    </div>
  );
}