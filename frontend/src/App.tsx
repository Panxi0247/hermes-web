import { useState, useEffect } from "react";
import "./App.css";
import Chat from "./components/Chat";
import ChatHistory from "./components/ChatHistory";
import Schedule from "./components/Schedule";
import { healthCheck } from "./api/chat";

type Message = {
  role: "system" | "user" | "assistant";
  content: string;
};

// page: 頁面導航（對應左側導覽列）
type Page = "schedule" | "chat" | "settings" | "history";

export default function App() {
  const [page, setPage] = useState<Page>("schedule");
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<Message[]>([
    { role: "assistant", content: "嗨！我是你的行程助理，有什麼可以幫你的？" },
  ]);

  useEffect(() => {
    const check = async () => {
      const ok = await healthCheck();
      setConnected(ok);
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  const showError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  const handleLoadConversation = (messages: Message[]) => {
    setChatMessages(messages);
    setPage("chat");
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

        {/* 連線狀態 */}
        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${connected ? "ok" : "error"}`} />
            <span className="status-text">
              {connected ? "已連接" : "未連接"}
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
            onError={showError}
            messages={chatMessages}
            onMessagesChange={setChatMessages}
          />
        )}
        {page === "settings" && (
          <div className="settings-placeholder">Settings — coming soon</div>
        )}
        {page === "history" && (
          <ChatHistory
            onLoadConversation={handleLoadConversation}
            currentMessages={chatMessages}
          />
        )}
      </main>
    </div>
  );
}