import { useState, useRef, useEffect } from "react";
import type { Message } from "../types";

interface ChatProps {
  onError: (msg: string) => void;
  messages: Message[];
  onMessagesChange: (msgs: Message[] | ((prev: Message[]) => Message[])) => void;
}

// WebSocket URL：讀取環境變數（Vite 會把 VITE_ 前綴的變數注入）
// 開發時預設 localhost，生產部署時改為伺服器 IP 或網域名稱
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8767";

export default function Chat({ onError, messages, onMessagesChange }: ChatProps) {
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 自動滾到底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 連線 / 重連
  useEffect(() => {
    let ws: WebSocket;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        onError("連線錯誤，嘗試重新連接...");
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.error) {
            onError(data.error);
            return;
          }
          if (data.type === "chunk" && data.done) {
            onMessagesChange((prev) => {
              const updated = [...prev];
              if (updated.length > 0 && updated[updated.length - 1].role === "assistant") {
                updated[updated.length - 1] = { role: "assistant", content: data.content };
              }
              return updated;
            });
          }
        } catch {
          // ignore parse errors
        }
      };
    };

    connect();

    return () => {
      closed = true;
      ws?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = () => {
    const content = input.trim();
    if (!content || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    setInput("");
    const userMsg: Message = { role: "user", content };
    onMessagesChange((prev) => [...prev, userMsg]);
    onMessagesChange((prev) => [...prev, { role: "assistant", content: "" }]);

    const historyMsgs = [...messages, userMsg];
    wsRef.current.send(
      JSON.stringify({
        messages: historyMsgs,
        model: "minimaxai/minimax-m2.7",
      })
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div>
          <p className="eyebrow">Chat</p>
          <h2>Hermes 對話</h2>
        </div>
        <div className={`ws-status ${connected ? "connected" : "disconnected"}`}>
          <span className="ws-dot" />
          {connected ? "已連接" : "連線中..."}
        </div>
      </div>

      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="avatar">{msg.role === "user" ? "U" : "H"}</div>
            <div className="bubble">{msg.content}</div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="輸入訊息..."
            rows={1}
            disabled={!connected}
          />
          <button
            onClick={sendMessage}
            disabled={!connected || !input.trim()}
          >
            {connected ? "➤" : "×"}
          </button>
        </div>
      </div>
    </div>
  );
}
