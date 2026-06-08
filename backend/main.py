"""
Hermes Web Backend - FastAPI server
Provides OpenAI-compatible API + WebSocket terminal
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import datetime
import httpx
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Hermes Web Backend starting on port {PORT}")
    print(f"Proxying to Hermes at {HERMES_HOST}:{HERMES_PORT}")
    yield
    # Shutdown
    await http_client.aclose()


# FastAPI app
app = FastAPI(title="Hermes Web Backend", version="1.0.0", lifespan=lifespan)

# CORS - 允許前端跨域請求，來源由環境變數控制
# FRONTEND_ORIGIN 格式如：http://192.168.1.100:5173
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
ALLOWED_ORIGINS = [
    FRONTEND_ORIGIN,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # 明確列舉，符合 CORS 規範（credentials 模式禁用萬用字元）
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


# --- WebSocket Terminal ---
def validate_allowed_command(command: str, args: List[str]) -> Optional[str]:
    if command not in ALLOWED_COMMANDS:
        return f"Command not allowed: {command}\nAvailable commands: {', '.join(ALLOWED_COMMANDS.keys())}\n"

    spec = ALLOWED_COMMANDS[command]
    if len(args) < spec["args"]:
        return f"Usage: {spec['description']}\n"

    return None


def execute_allowed_command(command: str, args: List[str], *, allow_ls_path: bool = False) -> str:
    if command == "echo":
        return " ".join(args) + "\n"
    if command == "date":
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S\n")
    if command == "pwd":
        return os.getcwd() + "\n"
    if command == "ls":
        path = args[0] if allow_ls_path and args else "."
        entries = os.listdir(path)
        return "  ".join(sorted(entries)) + "\n"
    if command == "whoami":
        return os.getenv("USER", "unknown") + "\n"
    return ""


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
        
        validation_error = validate_allowed_command(command, args)
        if validation_error:
            await self.send_output(validation_error, stream_end=True)
            return
        
        try:
            await self.send_output(execute_allowed_command(command, args), stream_end=True)
        except Exception as e:
            await self.send_output(f"Error: {e}\n", stream_end=True)


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
    validation_error = validate_allowed_command(req.command, req.args)
    if validation_error and req.command not in ALLOWED_COMMANDS:
        raise HTTPException(
            status_code=403, 
            detail=f"Command '{req.command}' not in whitelist. Available: {list(ALLOWED_COMMANDS.keys())}"
        )
    
    if validation_error:
        return CliResponse(
            output="",
            error=validation_error.strip()
        )
    
    try:
        output = execute_allowed_command(req.command, req.args, allow_ls_path=True)
        return CliResponse(output=output)
    except Exception as e:
        return CliResponse(output="", error=str(e))


# --- Crawl Endpoint ---
class CrawlRequest(BaseModel):
    url: str
    max_links: int = 10  # 回傳的連結數量上限


class CrawlResponse(BaseModel):
    url: str
    title: Optional[str] = None
    content: Optional[str] = None  # 去除 HTML 標籤的文字內容
    links: List[str] = []
    status_code: Optional[int] = None
    error: Optional[str] = None


@app.post("/api/crawl", response_model=CrawlResponse)
async def crawl_page(req: CrawlRequest):
    """
    使用 requests + BeautifulSoup 爬取網頁。
    適合純 HTML 靜態頁面，無法處理 JavaScript 動態內容。
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; HermesBot/1.0; +http://hermes.local)"
        }
        resp = requests.get(req.url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 取得標題
        title = None
        if soup.title:
            title = soup.title.string
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # 去除 script/style/nav/footer 等無用標籤
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 取得純文字內容（保留段落）
        content_parts = []
        for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
            text = p.get_text(strip=True)
            if text:
                content_parts.append(text)
        content = "\n\n".join(content_parts)

        # 取得連結（絕對 URL，限 max_links 個）
        links = []
        base = resp.url
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                links.append(href)
            elif href.startswith("/"):
                links.append(urljoin(base, href))
            if len(links) >= req.max_links:
                break

        return CrawlResponse(
            url=resp.url,
            title=title,
            content=content,
            links=links,
            status_code=resp.status_code,
        )
    except requests.exceptions.Timeout:
        return CrawlResponse(url=req.url, error="請求逾時（15秒）")
    except requests.exceptions.HTTPError as e:
        return CrawlResponse(url=req.url, error=f"HTTP 錯誤: {e.response.status_code}")
    except requests.exceptions.RequestException as e:
        return CrawlResponse(url=req.url, error=f"請求失敗: {str(e)}")


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
            "crawl": "POST /api/crawl",
            "health": "GET /health",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
