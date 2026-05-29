import { useState, useEffect, useRef } from "react";

type Message = {
  role: "system" | "user" | "assistant";
  content: string;
};

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number; // timestamp
};

const STORAGE_KEY = "hermes_conversations";

function loadConversations(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveConversations(convs: Conversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
}

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

function formatTime(ts: number) {
  const d = new Date(ts);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return d.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" }) + " " + d.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
}

function previewText(messages: Message[]) {
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  return lastUser ? lastUser.content.slice(0, 40) + (lastUser.content.length > 40 ? "..." : "") : "新對話";
}

interface ChatHistoryProps {
  onLoadConversation: (messages: Message[]) => void;
  currentMessages: Message[];
}

export default function ChatHistory({ onLoadConversation, currentMessages }: ChatHistoryProps) {
  // Lazy init: 只在初次 mount 時讀 localStorage，之後靠 ref 更新
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const savedRef = useRef(conversations);

  // auto-save currentMessages 到 localStorage（debounce 避免每次 keystroke 都寫）
  useEffect(() => {
    if (currentMessages.length <= 1) return;
    const saved = savedRef.current;
    const title = previewText(currentMessages);
    const newConv: Conversation = {
      id: saved[0]?.id || generateId(),
      title,
      messages: currentMessages,
      updatedAt: Date.now(),
    };
    const updated = [newConv, ...saved.filter((c) => c.id !== newConv.id)];
    savedRef.current = updated;
    saveConversations(updated);
    // 不在這裡 setConversations，避免連鎖 render
  }, [currentMessages]);

  const handleNewChat = () => {
    // 先把目前對話儲存
    if (currentMessages.length > 1) {
      const existing = savedRef.current[0];
      const newConv: Conversation = existing
        ? { ...existing, messages: currentMessages, updatedAt: Date.now() }
        : {
            id: generateId(),
            title: previewText(currentMessages),
            messages: currentMessages,
            updatedAt: Date.now(),
          };
      const updated = [newConv, ...savedRef.current.filter((c) => c.id !== newConv.id)];
      saveConversations(updated);
      savedRef.current = updated;
      setConversations(updated);
    }
    onLoadConversation([{ role: "assistant", content: "嗨！我是 Hermes，有什麼可以幫你的？" }]);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = savedRef.current.filter((c) => c.id !== id);
    savedRef.current = updated;
    saveConversations(updated);
    setConversations(updated);
  };

  return (
    <div className="chat-history">
      <div className="history-header">
        <h2>歷史紀錄</h2>
        <button className="btn-new-chat" onClick={handleNewChat}>+ 新對話</button>
      </div>

      <div className="history-list">
        {conversations.length === 0 && (
          <div className="history-empty">尚無對話紀錄</div>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className="history-item"
            onClick={() =>
              onLoadConversation([
                { role: "assistant", content: "嗨！我是 Hermes，有什麼可以幫你的？" },
                ...conv.messages,
              ])
            }
          >
            <div className="history-item-content">
              <div className="history-title">{conv.title || previewText(conv.messages)}</div>
              <div className="history-time">{formatTime(conv.updatedAt)}</div>
            </div>
            <button
              className="history-delete"
              onClick={(e) => handleDelete(conv.id, e)}
              aria-label="刪除"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

