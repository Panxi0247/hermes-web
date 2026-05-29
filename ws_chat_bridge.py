#!/usr/bin/env python3
"""
Hermes WebSocket Chat Bridge
WebSocket → Hermes REST API (streaming SSE)
避免瀏覽器 CORS 問題
智慧資訊推薦：偵測使用者興趣，主動拿相關新聞/文章推薦
"""
import asyncio
import json
import re
import subprocess
import sys
import websockets
import httpx
from datetime import datetime
from urllib.parse import quote

HERMES_HOST = "127.0.0.1"
HERMES_PORT = 8642
WS_PORT = 8767


# ─── 通用意圖偵測：是否為推薦資訊類查詢 ───

RECOMMEND_PATTERNS = [
    # 中文
    r"有.*推薦", r"推薦.*", r"值得.*看", r"有.*值得",
    r"最近.*怎麼", r"最近.*發展", r"最近.*進展", r"最近.*動態",
    r"有.*新聞", r"有.*報導", r"有.*文章", r"想了解", r"想知",
    r"想看.*關於", r"給我.*關於", r"幫我找.*", r"有什麼.*推薦",
    r"有什麼新鮮事", r"最近有什麼",
    # 英文
    r"recommend", r"suggest", r"worth reading", r"worth watching",
    r"what's happening", r"what happened", r"latest on",
    r"can you tell me about", r"i'm interested in",
]

STOPWORDS = {
    # 中文通用詞
    "的", "是", "在", "有", "和", "與", "了", "嗎", "呢", "吧", "啊",
    "我", "你", "他", "她", "它", "我們", "你們", "他們", "大家",
    "這", "那", "什麼", "怎麼", "為什麼", "如何", "哪", "哪些",
    "一下", "些", "一點", "個", "別人",
    "可以", "能", "會", "要", "想", "覺得",
    "最近", "現在", "目前", "今天", "明天", "昨天",
    "情況", "消息", "進展", "最新",
    "推薦", "值得", "幫我", "給我", "想了解", "想知道",
    "請問", "有什麼", "沒", "沒什麼",
    # 英文通用詞
    "please", "can", "could", "would", "i", "me", "my", "you", "your",
    "a", "an", "the", "is", "are", "was", "were", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "what", "when", "where",
    "how", "who", "which", "that", "this", "these", "those",
}


def detect_recommendation_intent(user_message: str) -> bool:
    """偵測是否為推薦/資訊查詢意圖"""
    for pattern in RECOMMEND_PATTERNS:
        if re.search(pattern, user_message, re.IGNORECASE):
            return True
    return False


def extract_topic_keywords(user_message: str) -> str:
    """從使用者訊息中抽取感興趣的主題關鍵字（支援中英文混合）"""
    text = re.sub(r'[^\w\s]', ' ', user_message)

    # 取出中文序列（整段）、英文單字
    chinese_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
    english_words = re.findall(r'[a-zA-Z0-9]+', text)

    all_keywords = []
    for seq in chinese_seqs:
        if seq not in STOPWORDS:
            all_keywords.append(seq)

    for w in english_words:
        if w.lower() not in STOPWORDS and len(w) > 1:
            all_keywords.append(w)

    return " ".join(all_keywords[:5])


# ─── 新聞推薦：curl Google News RSS 搜尋 ───

def fetch_news_for_topic(keywords: str) -> str:
    """用 curl + Google News RSS 拿指定主題的新聞"""
    if not keywords.strip():
        return ""

    try:
        encoded = quote(keywords)
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "12", rss_url],
            capture_output=True, text=True
        )
        xml = result.stdout

        items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
        if not items:
            return ""

        news_list = []
        for item in items[:12]:
            title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item)
            if not title_m:
                title_m = re.search(r'<title>(.*?)</title>', item)
            date_m = re.search(r'<pubDate>(.*?)</pubDate>', item)
            source_m = re.search(r'<source>(.*?)</source>', item)

            title = title_m.group(1).strip() if title_m else "無標題"
            title = re.sub(r'<[^>]+>', '', title)

            date_raw = date_m.group(1).strip() if date_m else ""
            try:
                dt_obj = datetime.strptime(date_raw, "%a, %d %b %Y %H:%M:%S GMT")
                date_str = dt_obj.strftime("%m/%d %H:%M")
            except ValueError:
                date_str = ""

            source = source_m.group(1).strip() if source_m else ""
            if source:
                news_list.append(f"[{date_str}] {title}（{source}）")
            else:
                news_list.append(f"[{date_str}] {title}")

        if not news_list:
            return ""

        now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        lines = [f"📰 「{keywords}」相關新聞（Google News，{now_str}）\n"]
        lines.extend(news_list)
        return "\n".join(lines)
    except Exception as e:
        return f"[新聞抓取失敗: {e}]"


# ─── 維基百科條目 ───

def fetch_wikipedia_summary(keywords: str) -> str:
    """拿維基百科條目摘要"""
    if not keywords.strip():
        return ""

    try:
        encoded = quote(keywords)
        url = f"https://zh.wikipedia.org/wiki/{encoded}"
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", "-L", url],
            capture_output=True, text=True
        )
        html = result.stdout

        content_area = re.search(r'id="mw-content-text"(.*?)</div>', html, re.DOTALL)
        if not content_area:
            return ""

        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content_area.group(1), re.DOTALL)
        for para in paragraphs[:3]:
            text = re.sub(r'<[^>]+>', '', para).strip()
            text = re.sub(r'\[.*?\]', '', text)
            if len(text) > 50:
                if len(text) > 500:
                    text = text[:500] + "..."
                now_str = datetime.now().strftime("%Y年%m月%d日")
                return f"📖 維基百科「{keywords}」摘要（{now_str}）\n\n{text}\n\n來源：{url}"

        return ""
    except Exception:
        return ""


# ─── 主 Bridge 邏輯 ───

async def bridge_to_hermes(messages: list, model: str) -> str:
    """呼叫 Hermes REST streaming，回傳完整回應"""
    hermes_payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    headers = {
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"http://{HERMES_HOST}:{HERMES_PORT}/v1/chat/completions",
                json=hermes_payload,
                headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    return json.dumps({"error": f"HTTP {resp.status_code}: {text.decode()}"})

                full_content = ""
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            continue
                        try:
                            json_data = json.loads(data)
                            content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                full_content += content
                        except json.JSONDecodeError:
                            pass
                return json.dumps({"content": full_content})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def chat_handler(websocket):
    """處理客戶端 WebSocket 連線"""
    client_host = websocket.remote_address
    print(f"[WS] Client connected: {client_host}")

    try:
        async for raw_msg in websocket:
            try:
                msg = json.loads(raw_msg)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON"}))
                continue

            messages = msg.get("messages", [])
            model = msg.get("model", "minimaxai/minimax-m2.7")

            if not messages:
                await websocket.send(json.dumps({"error": "No messages provided"}))
                continue

            last_msg = messages[-1]
            user_text = last_msg.get("content", "") if isinstance(last_msg, dict) else ""

            # ── 智慧資訊推薦 ──
            if detect_recommendation_intent(user_text):
                keywords = extract_topic_keywords(user_text)
                print(f"[Info Fallback] 偵測到推薦意圖，關鍵字:「{keywords}」")

                if keywords:
                    # 先拿新聞
                    news_data = fetch_news_for_topic(keywords)
                    if news_data and len(news_data) > 50:
                        print(f"[Info Fallback] 拿到新聞，長度: {len(news_data)} 字")
                        context_msg = {
                            "role": "system",
                            "content": (
                                f"【以下是你可以使用的參考資料，不需要再呼叫搜尋工具】\n\n"
                                f"{news_data}\n\n"
                                f"請根據以上資料，主動推薦用戶值得關注的內容，並簡要說明為什麼值得看。"
                            )
                        }
                        messages = [context_msg] + messages
                    else:
                        # 新聞太少，試維基
                        wiki_data = fetch_wikipedia_summary(keywords)
                        if wiki_data:
                            print(f"[Info Fallback] 拿到維基摘要，長度: {len(wiki_data)} 字")
                            context_msg = {
                                "role": "system",
                                "content": (
                                    f"【以下是你可以使用的參考資料，不需要再呼叫搜尋工具】\n\n"
                                    f"{wiki_data}\n\n"
                                    f"請根據以上資料，主動推薦用戶值得關注的內容，並簡要說明為什麼值得了解。"
                                )
                            }
                            messages = [context_msg] + messages

            result = await bridge_to_hermes(messages, model)

            try:
                result_data = json.loads(result)
                if "error" in result_data:
                    await websocket.send(json.dumps({"error": result_data["error"]}))
                else:
                    content = result_data.get("content", "")
                    await websocket.send(json.dumps({
                        "type": "chunk",
                        "content": content,
                        "done": True,
                    }))
            except Exception as e:
                await websocket.send(json.dumps({"error": str(e)}))

    except websockets.exceptions.ConnectionClosedOK:
        print(f"[WS] Client disconnected: {client_host}")
    except Exception as e:
        print(f"[WS] Error: {e}")
        try:
            await websocket.send(json.dumps({"error": str(e)}))
        except:
            pass


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else WS_PORT
    print(f"[WS] Hermes WebSocket Chat Bridge starting on ws://0.0.0.0:{port}")
    print(f"[WS] → Proxying to http://{HERMES_HOST}:{HERMES_PORT}")

    async with websockets.serve(chat_handler, "0.0.0.0", port):
        print(f"[WS] Ready. Connect at ws://localhost:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())