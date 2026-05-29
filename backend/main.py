"""
Hermes Web Backend - FastAPI server
Provides OpenAI-compatible API + WebSocket terminal
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import httpx
import asyncio
import json
import os

# Config
HERMES_HOST = os.getenv("HERMES_HOST", "127.0.0.1")
HERMES_PORT = int(os.getenv("HERMES_PORT", "8642"))
API_KEY = os.getenv("API_KEY", "hermes-client-key")
PORT = 8000

# Allowed CLI commands (whitelist)
ALLOWED_COMMANDS = {
    "echo": {"args": 1, "description": "echo <text>"},
    "date": {"args": 0, "description": "Show current date/time"},
    "pwd": {"args": 0, "description": "Print working directory"},
    "ls": {"args": 0, "description": "List directory contents"},
    "whoami": {"args": 0, "description": "Current user"},
}

# FastAPI app
app = FastAPI(title="Hermes Web Backend", version="1.0.0")

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP client for Hermes
http_client = httpx.AsyncClient(timeout=120.0)


# --- Pydantic Models ---
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "hermes-agent"
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None


class DeltaContent(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    finish_reason: Optional[str] = None


class StreamChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[dict]


# --- WebSocket Terminal ---
class TerminalSession:
    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.command_history: List[str] = []

    async def send_output(self, text: str, stream_end: bool = False):
        await self.ws.send_json({
            "type": "output",
            "text": text,
            "stream_end": stream_end
        })

    async def execute_command(self, cmd: str):
        parts = cmd.strip().split()
        if not parts:
            return
        
        command = parts[0]
        args = parts[1:]
        
        if command not in ALLOWED_COMMANDS:
            await self.send_output(f"Command not allowed: {command}\n")
            await self.send_output(f"Available commands: {', '.join(ALLOWED_COMMANDS.keys())}\n", stream_end=True)
            return
        
        spec = ALLOWED_COMMANDS[command]
        if len(args) < spec["args"]:
            await self.send_output(f"Usage: {spec['description']}\n", stream_end=True)
            return
        
        # Execute whitelisted commands
        if command == "echo":
            await self.send_output(" ".join(args) + "\n", stream_end=True)
        elif command == "date":
            import datetime
            await self.send_output(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S\n"), stream_end=True)
        elif command == "pwd":
            await self.send_output(os.getcwd() + "\n", stream_end=True)
        elif command == "ls":
            try:
                entries = os.listdir(".")
                await self.send_output("  ".join(sorted(entries)) + "\n", stream_end=True)
            except Exception as e:
                await self.send_output(f"Error: {e}\n", stream_end=True)
        elif command == "whoami":
            await self.send_output(os.getenv("USER", "unknown") + "\n", stream_end=True)


terminal_sessions: List[TerminalSession] = []


@app.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket):
    await websocket.accept()
    session = TerminalSession(websocket)
    terminal_sessions.append(session)
    
    try:
        # Send welcome
        await session.send_output("Hermes Terminal (whitelist mode)\n")
        await session.send_output(f"Available: {', '.join(ALLOWED_COMMANDS.keys())}\n")
        await session.send_output("> ", stream_end=False)
        
        while True:
            data = await websocket.receive_text()
            session.command_history.append(data)
            
            if data.strip():
                await session.execute_command(data)
            
            await session.send_output("> ", stream_end=False)
            
    except WebSocketDisconnect:
        pass
    finally:
        terminal_sessions.remove(session)


# --- Chat Completions (OpenAI-compatible) ---
async def _hermes_stream_generator(hermes_payload: dict, headers: dict):
    """Async generator that streams from Hermes and yields SSE bytes"""
    try:
        async with http_client.stream(
            "POST",
            f"http://{HERMES_HOST}:{HERMES_PORT}/v1/chat/completions",
            json=hermes_payload,
            headers=headers,
        ) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                yield f'{{"error": "Hermes HTTP {resp.status_code}", "detail": "{text.decode()}"}}\n'.encode()
                return
            
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield f"{line}\n".encode()
            yield b"data: [DONE]\n\n"
    except Exception as e:
        yield f'{{"error": "{str(e)}"}}\n'.encode()


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    Proxy to Hermes API at 127.0.0.1:8642
    Supports streaming and non-streaming
    """
    hermes_payload = {
        "model": req.model,
        "messages": [{"role": m.role, "content": m.content} for m in req.messages],
        "stream": req.stream,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    
    if req.stream:
        return StreamingResponse(
            _hermes_stream_generator(hermes_payload, headers),
            media_type="text/event-stream",
        )
    else:
        try:
            hermes_resp = await http_client.post(
                f"http://{HERMES_HOST}:{HERMES_PORT}/v1/chat/completions",
                json=hermes_payload,
                headers=headers,
            )
            if hermes_resp.status_code != 200:
                raise HTTPException(status_code=hermes_resp.status_code, detail=hermes_resp.text)
            return hermes_resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Gateway timeout")
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Hermes error: {str(e)}")


# --- CLI Command Endpoint (whitelist only) ---
class CliRequest(BaseModel):
    command: str
    args: List[str] = []

class CliResponse(BaseModel):
    output: str
    error: Optional[str] = None


@app.post("/api/cli", response_model=CliResponse)
async def run_cli(req: CliRequest):
    """Execute a whitelisted CLI command"""
    if req.command not in ALLOWED_COMMANDS:
        raise HTTPException(
            status_code=403, 
            detail=f"Command '{req.command}' not in whitelist. Available: {list(ALLOWED_COMMANDS.keys())}"
        )
    
    spec = ALLOWED_COMMANDS[req.command]
    if len(req.args) < spec["args"]:
        return CliResponse(
            output="",
            error=f"Usage: {spec['description']}"
        )
    
    try:
        if req.command == "echo":
            output = " ".join(req.args) + "\n"
        elif req.command == "date":
            import datetime
            output = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S\n")
        elif req.command == "pwd":
            output = os.getcwd() + "\n"
        elif req.command == "ls":
            entries = os.listdir("." if not req.args else req.args[0])
            output = "  ".join(sorted(entries)) + "\n"
        elif req.command == "whoami":
            output = os.getenv("USER", "unknown") + "\n"
        else:
            output = ""
        
        return CliResponse(output=output)
    except Exception as e:
        return CliResponse(output="", error=str(e))


# --- Health ---
@app.get("/health")
async def health():
    return {"status": "ok", "backend": "hermes-web"}


@app.get("/")
async def root():
    return {
        "name": "Hermes Web Backend",
        "version": "1.0.0",
        "endpoints": {
            "chat": "POST /v1/chat/completions",
            "terminal": "WS /ws/terminal",
            "cli": "POST /api/cli",
            "health": "GET /health",
        }
    }


# --- Startup ---
@app.on_event("startup")
async def startup():
    print(f"Hermes Web Backend starting on port {PORT}")
    print(f"Proxying to Hermes at {HERMES_HOST}:{HERMES_PORT}")

@app.on_event("shutdown")
async def shutdown():
    await http_client.aclose()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")