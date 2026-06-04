import type { Conversation, Message } from "../types";

const STORAGE_KEY = "hermes_conversations";

export const welcomeMessage: Message = {
  role: "assistant",
  content: "嗨！我是 Hermes，有什麼可以幫你的？",
};

const generateId = () => Math.random().toString(36).slice(2, 10);

export function getWelcomeMessages(): Message[] {
  return [welcomeMessage];
}

export function loadConversations(): Conversation[] {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (!value) return [];
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveConversations(conversations: Conversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

export function previewText(messages: Message[]) {
  const lastUser = [...messages].reverse().find((message) => message.role === "user");
  if (!lastUser) return "新對話";
  return lastUser.content.slice(0, 40) + (lastUser.content.length > 40 ? "..." : "");
}

export function upsertConversation(
  conversations: Conversation[],
  messages: Message[],
  conversationId: string | null
) {
  const id = conversationId ?? generateId();
  const conversation: Conversation = {
    id,
    title: previewText(messages),
    messages,
    updatedAt: Date.now(),
  };

  return {
    conversationId: id,
    conversations: [conversation, ...conversations.filter((item) => item.id !== id)],
  };
}

export function formatConversationTime(timestamp: number) {
  const date = new Date(timestamp);
  const now = new Date();
  const time = date.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });

  if (date.toDateString() === now.toDateString()) return time;
  return `${date.toLocaleDateString("zh-TW", { month: "numeric", day: "numeric" })} ${time}`;
}
