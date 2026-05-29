import { useState, useEffect, useRef } from "react";
import { TerminalClient, runCliCommand } from "../api/terminal";

type TerminalEventType = "output" | "error" | "connected" | "disconnected";
interface TerminalEvent {
  type: TerminalEventType;
  text?: string;
  stream_end?: boolean;
}

interface TerminalProps {
  onError: (msg: string) => void;
}

const COMMANDS = ["echo", "date", "pwd", "ls", "whoami"];

export default function Terminal({ onError }: TerminalProps) {
  const [output, setOutput] = useState<string[]>([
    "Hermes Terminal (whitelist mode)",
    `可用指令: ${COMMANDS.join(", ")}`,
    "",
  ]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<TerminalClient | null>(null);

  useEffect(() => {
    const client = new TerminalClient();
    clientRef.current = client;

    const unsub = client.onMessage((event: TerminalEvent) => {
      if (event.type === "connected") {
        setConnected(true);
        setOutput((prev) => [...prev, "[已連接]"]);
      } else if (event.type === "disconnected") {
        setConnected(false);
        setOutput((prev) => [...prev, "[已斷線]"]);
      } else if (event.type === "output" && event.text) {
        setOutput((prev) => [...prev, event.text!]);
      } else if (event.type === "error" && event.text) {
        setOutput((prev) => [...prev, `Error: ${event.text}`]);
        onError(event.text);
      }
    });

    client.connect();

    return () => {
      unsub();
      client.disconnect();
    };
  }, [onError]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView();
  }, [output]);

  const submit = (text: string) => {
    if (!text.trim()) return;
    setOutput((prev) => [...prev, `> ${text}`]);
    setInput("");
    clientRef.current?.send(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      submit(input);
    }
  };

  const runQuickCommand = async (cmd: string) => {
    try {
      const result = await runCliCommand(cmd, []);
      if (result.error) {
        setOutput((prev) => [...prev, `錯誤: ${result.error}`]);
        onError(result.error);
      } else {
        setOutput((prev) => [...prev, result.output]);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Command failed";
      setOutput((prev) => [...prev, `Error: ${message}`]);
      onError(message);
    }
  };

  return (
    <div className="terminal-container">
      <div className="terminal-header">
        <span>終端機</span>
        <span className={`status ${connected ? "ok" : "error"}`}>
          {connected ? "已連接" : "連線中..."}
        </span>
      </div>

      <div className="terminal-commands">
        {COMMANDS.map((cmd) => (
          <button key={cmd} onClick={() => runQuickCommand(cmd)} disabled={!connected}>
            {cmd}
          </button>
        ))}
      </div>

      <div className="terminal-output">
        {output.map((line, i) => (
          <div key={i} className={line.startsWith("[") ? "status-line" : ""}>
            {line}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="terminal-input">
        <span className="prompt">$</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="輸入指令..."
          disabled={!connected}
        />
      </div>
    </div>
  );
}
