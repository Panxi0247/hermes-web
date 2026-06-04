export interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number;
}

export interface ChatCompletionRequest {
  model: string;
  messages: Message[];
  stream: boolean;
}
