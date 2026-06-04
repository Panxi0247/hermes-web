// API URL：讀取環境變數，生產部署時改為伺服器 IP:Port
const API_BASE = import.meta.env.VITE_API_URL || "";

export type Message = {
  role: "system" | "user" | "assistant";
  content: string;
};

export interface ChatCompletionRequest {
  model: string;
  messages: Message[];
  stream: boolean;
}

export async function* streamChat(
  messages: Message[],
  model: string = "hermes-agent"
): AsyncGenerator<string> {
  // 使用 non-streaming 避免 Hermes CORS+streaming 403 問題
  const response = await fetch(`${API_BASE}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, stream: false }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`HTTP ${response.status}: ${error}`);
  }

  const data = await response.json();
  const content = data.choices?.[0]?.message?.content ?? "";
  if (content) yield content;
}

export async function nonStreamChat(
  messages: Message[],
  model: string = "hermes-agent"
): Promise<string> {
  const response = await fetch(`${API_BASE}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, stream: false }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`HTTP ${response.status}: ${error}`);
  }

  const data = await response.json();
  return data.choices?.[0]?.message?.content ?? "";
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
