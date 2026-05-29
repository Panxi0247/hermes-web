const WS_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";
const WS_BASE = `${WS_PROTOCOL}//${window.location.host}`;

export type TerminalEventType = "output" | "error" | "connected" | "disconnected";

export type TerminalEvent = {
  type: TerminalEventType;
  text?: string;
  stream_end?: boolean;
};

export class TerminalClient {
  private ws: WebSocket | null = null;
  private listeners: ((event: TerminalEvent) => void)[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(`${WS_BASE}/ws/terminal`);

    this.ws.onopen = () => {
      this.emit({ type: "connected" });
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.emit({ type: "output", text: data.text, stream_end: data.stream_end });
      } catch {
        this.emit({ type: "output", text: event.data });
      }
    };

    this.ws.onclose = () => {
      this.emit({ type: "disconnected" });
      // Auto-reconnect after 3s
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = () => {
      this.emit({ type: "error", text: "WebSocket error" });
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  send(text: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(text);
    }
  }

  onMessage(listener: (event: TerminalEvent) => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private emit(event: TerminalEvent) {
    this.listeners.forEach((l) => l(event));
  }
}

export async function runCliCommand(
  command: string,
  args: string[] = []
): Promise<{ output: string; error?: string }> {
  const res = await fetch("/api/cli", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, args }),
  });

  if (!res.ok) {
    const data = await res.json();
    return { output: "", error: data.detail || `HTTP ${res.status}` };
  }

  return res.json();
}
