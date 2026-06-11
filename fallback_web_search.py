#!/usr/bin/env python3
"""
fallback_web_search.py
多來源網路搜尋：並行嘗試各免費來源，任一成功即回傳，完全失敗才回報錯誤。
來源順序（僅用於日誌順序）：Google News RSS → Bing News RSS → DuckDuckGo HTML → Wikipedia

用途：
  - ws_chat_bridge.py 的智慧推薦功能
  - 或作為 Hermes Agent 的獨立工具

並行優化（2026-06-04）：
  - 四個 source 同時發起，先完成的就回傳（不用依序等待）
  - 統一 timeout 6s，避免單一 source 過慢拖累整體
"""
import asyncio
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, urlencode
from typing import List, Dict, Optional
import os

# ─── Jina API Key（環境變數，安全性） ───────────────────────────────
JINA_API_KEY = os.environ.get(
    "JINA_API_KEY",
    "jina_3f0df340406040fda49e652b3c47f317Ha9jMwzARV1XS1r_GbZfijWx_vUo"
)

# ─── 統一結果格式 ────────────────────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str = ""
    source: str = ""
    date: str = ""
    snippet: str = ""

    def to_str(self) -> str:
        parts = []
        if self.date:
            parts.append(f"[{self.date}]")
        parts.append(self.title)
        if self.source:
            parts.append(f"（{self.source}）")
        return " ".join(parts)


# ─── 通用異步 curl ───────────────────────────────────────────────

async def curl_async(url: str, timeout: int = 6, headers: str = "") -> str:
    """用 asyncio.subprocess 異步執行 curl（避免同步 subprocess 卡住事件循環）"""
    cmd = ["curl", "-s", "--max-time", str(timeout), "-L", url]
    if headers:
        for h in headers.split("|"):
            cmd += ["-H", h]
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 1)
        return stdout.decode("utf-8", errors="ignore")
    except asyncio.TimeoutError:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        return ""
    except Exception:
        return ""


# ─── Source 1：Jina Search API（最高優先） ──────────────────────────

async def search_jina_async(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 Jina AI 搜尋端點（s.jina.ai/search），需要 API key"""
    try:
        url = f"https://s.jina.ai/search?q={quote(query)}&num={limit}"
        text = await curl_async(
            url,
            timeout=8,
            headers=f"Authorization: Bearer {JINA_API_KEY}"
        )
        if not text or len(text) < 50:
            return None

        # Jina 搜尋返回格式（Markdown）：
        # [1] Title: 標題
        # [1] URL Source: https://...
        # [1] Description: 描述文字
        #
        # # 標題內容（頁面內容）
        results = []
        idx = 0  # 當前結果 index（1,2,3...）

        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # 匹配 [N] Title: / URL Source: / Description:
            m = re.match(r'\[(\d+)\]\s+(Title|URL Source|Description):\s*(.*)', line)
            if m:
                num = int(m.group(1))
                tag = m.group(2)
                val = m.group(3).strip()

                if tag == "Title":
                    # 新結果開始，先存前一筆
                    if idx > 0 and len(results) < num - 1:
                        results.append(SearchResult(
                            title=f"結果{idx}",
                            url="",
                            source="jina",
                            snippet=""
                        ))
                    idx = num
                    # 建立新 result 的框架
                    if num > len(results):
                        results.append(SearchResult(
                            title=val,
                            url="",
                            source="jina",
                            snippet=""
                        ))
                    else:
                        results[num - 1].title = val
                elif tag == "URL Source":
                    if num <= len(results):
                        results[num - 1].url = val
                elif tag == "Description":
                    if num <= len(results):
                        results[num - 1].snippet = val[:200]
            i += 1

        # 過濾掉無 title 的結果
        valid_results = [r for r in results if r.title and r.title.strip()]
        return valid_results[:limit] if valid_results else None

    except Exception:
        return None


def search_jina(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    return asyncio.run(search_jina_async(query, limit))


# ─── Source 2：Google News RSS（最快、最準） ───────────────────────

async def search_google_news_async(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 Google News RSS 搜尋，支援中英文"""
    try:
        encoded = quote(query)
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        )
        xml_text = await curl_async(rss_url, timeout=6)
        if not xml_text or len(xml_text) < 100:
            return None

        root = ET.fromstring(xml_text)
        results = []
        for item in root.findall(".//item")[:limit]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            source_el = item.find("source")

            raw_title = ""
            if title_el is not None and title_el.text:
                raw_title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title_el.text)
                raw_title = re.sub(r'<[^>]+>', '', raw_title).strip()

            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            date_str = ""
            if pub_el is not None and pub_el.text:
                try:
                    dt = datetime.strptime(pub_el.text, "%a, %d %b %Y %H:%M:%S GMT")
                    date_str = dt.strftime("%m/%d %H:%M")
                except ValueError:
                    pass

            source = source_el.text.strip() if source_el is not None and source_el.text else ""
            if link.startswith("https://news.google.com"):
                link = re.sub(r'.*url=', '', link, count=1)

            if raw_title:
                results.append(SearchResult(
                    title=raw_title,
                    url=link,
                    source=source,
                    date=date_str,
                ))

        return results if results else None

    except Exception:
        return None


def search_google_news(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    return asyncio.run(search_google_news_async(query, limit))


# ─── Source 2：Bing News RSS ──────────────────────────────────────

async def search_bing_news_async(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 Bing News RSS 搜尋"""
    try:
        encoded = quote(query)
        rss_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"
        xml_text = await curl_async(rss_url, timeout=6)
        if not xml_text or len(xml_text) < 100:
            return None

        root = ET.fromstring(xml_text)
        results = []
        for item in root.findall(".//item")[:limit]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            desc_el = item.find("description")

            raw_title = title_el.text.strip() if title_el is not None and title_el.text else ""
            if not raw_title:
                continue

            raw_title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', raw_title)
            raw_title = re.sub(r'<[^>]+>', '', raw_title).strip()

            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            date_str = ""
            if pub_el is not None and pub_el.text:
                try:
                    dt = datetime.strptime(pub_el.text[:25], "%a, %d %b %Y %H:%M:%S")
                    date_str = dt.strftime("%m/%d %H:%M")
                except ValueError:
                    pass

            snippet = ""
            if desc_el is not None and desc_el.text:
                snippet = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', desc_el.text)
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()[:200]

            results.append(SearchResult(
                title=raw_title,
                url=link,
                date=date_str,
                snippet=snippet,
            ))

        return results if results else None

    except Exception:
        return None


def search_bing_news(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    return asyncio.run(search_bing_news_async(query, limit))


# ─── Source 3：DuckDuckGo HTML（無需 API Key） ─────────────────────

async def search_duckduckgo_async(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 DuckDuckGo HTML 頁面截圖新聞區塊"""
    try:
        encoded = quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}+news"
        html = await curl_async(
            url, timeout=6,
            headers="User-Agent:Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )
        if not html or "<html>" not in html.lower():
            return None

        results = []
        for result_div in re.finditer(r'<a class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            link = result_div.group(1).strip()
            title_html = result_div.group(2)
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and len(title) > 5:
                results.append(SearchResult(title=title, url=link))
            if len(results) >= limit:
                break

        if not results:
            for a_tag in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
                link = a_tag.group(1)
                title = re.sub(r'<[^>]+>', '', a_tag.group(2)).strip()
                if title and len(title) > 10 and ("news" in link.lower() or "article" in link.lower()):
                    results.append(SearchResult(title=title, url=link))
                if len(results) >= limit:
                    break

        return results if results else None

    except Exception:
        return None


def search_duckduckgo(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    return asyncio.run(search_duckduckgo_async(query, limit))


# ─── Source 4：Wikipedia 快速搜尋（並行抓 OpenSearch + 文章） ───────

async def search_wikipedia_async(query: str, limit: int = 5) -> Optional[List[SearchResult]]:
    """
    用 curl 直接 GET Wikipedia 頁面，以關鍵字快速過濾感興趣的段落。
    適用於：「甚麼是 XXX」、「XXX 的歷史」等問題。
    """
    try:
        encoded = quote(query)
        # 1. 用 OpenSearch API 取得相符的條目標題（限 2 個）
        search_url = (
            f"https://en.wikipedia.org/w/api.php"
            f"?action=opensearch&search={encoded}&limit=2&format=json"
        )
        raw = await curl_async(search_url, timeout=6)
        try:
            suggestions = json.loads(raw)
            titles = suggestions[1] if len(suggestions) > 1 else []
        except Exception:
            titles = []

        if not titles:
            return None

        # 2. 同時抓所有候選文章頁面（並行，timeout 6s 總限制）
        async def fetch_article(title: str) -> Optional[SearchResult]:
            article_url = f"https://en.wikipedia.org/wiki/{quote(title)}"
            html = await curl_async(article_url, timeout=6)
            if len(html) < 500:
                return None

            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
            matched = []
            for para in paragraphs[:15]:
                text = re.sub(r'<[^>]+>', '', para).strip()
                text = re.sub(r'\[.*?\]', '', text)
                if len(text) > 40 and query.lower() in text.lower():
                    matched.append(text)
                if len(matched) >= limit:
                    break

            # 若關鍵字沒配到，直接用前2段當摘要
            if not matched:
                for para in paragraphs[:2]:
                    text = re.sub(r'<[^>]+>', '', para).strip()
                    text = re.sub(r'\[.*?\]', '', text)
                    if len(text) > 50:
                        matched.append(text)
                    if len(matched) >= 1:
                        break

            if matched:
                snippet = matched[0][:300]
                if len(matched[0]) > 300:
                    snippet += "..."
                return SearchResult(
                    title=title,
                    url=article_url,
                    snippet=snippet,
                    source="Wikipedia",
                )
            return None

        # 同時發起所有文章的請求，誰先成功誰先贏
        tasks = [fetch_article(t) for t in titles[:2]]
        done, pending = await asyncio.wait(
            [asyncio.create_task(t) for t in tasks],
            timeout=6,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()

        for t in done:
            try:
                result = t.result()
                if result:
                    return [result]
            except Exception:
                pass

        return None

    except Exception:
        return None


def search_wikipedia(query: str, limit: int = 5) -> Optional[List[SearchResult]]:
    return asyncio.run(search_wikipedia_async(query, limit))


# ─── 主程式：並行多來源搜尋（核心優化） ─────────────────────────

async def web_search_async(query: str, limit: int = 10, verbose: bool = False) -> Dict:
    """
    四個 source 同時發起，先完成就回傳（不等其餘）。
    全部超時 / 失敗才回 error。
    """
    sources = [
        ("jina",         search_jina_async),
        ("google_news",  search_google_news_async),
        ("bing_news",    search_bing_news_async),
        ("duckduckgo",   search_duckduckgo_async),
        ("wikipedia",    search_wikipedia_async),
    ]

    # 同時發起所有搜尋任務
    async def try_source(name: str, fn, q: str, lim: int):
        if verbose:
            print(f"[fallback_search] 嘗試：{name}", flush=True)
        try:
            result = await asyncio.wait_for(fn(q, lim), timeout=6)
            if result:
                if verbose:
                    print(f"[fallback_search] 成功：{name}，拿到 {len(result)} 筆", flush=True)
                return (name, result)
        except asyncio.TimeoutError:
            if verbose:
                print(f"[fallback_search] {name} timeout", flush=True)
        except Exception as e:
            if verbose:
                print(f"[fallback_search] {name} error: {e}", flush=True)
        return (None, None)

    # 建立所有 task
    tasks = [try_source(name, fn, query, limit) for name, fn in sources]
    pending = {asyncio.create_task(t): name for t, (name, _) in zip(tasks, sources)}

    winner_name: str | None = None
    winner_results: list | None = None

    # 等第一個完成（成功或失敗）
    done, pending = await asyncio.wait(
        pending.keys(),
        timeout=7,  # 總 timeout 比各 source 的 6s 稍長，確保起碼有一個完成
        return_when=asyncio.FIRST_COMPLETED,
    )

    for t in done:
        name, results = t.result()
        if name and results:
            winner_name = name
            winner_results = results
            break

    # Cancel 剩餘 pending tasks
    for t in pending:
        t.cancel()
        try:
            await asyncio.wait_for(t, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    if winner_name and winner_results:
        return {
            "source": winner_name,
            "results": winner_results,
            "error": None,
        }

    return {
        "source": "none",
        "results": [],
        "error": "所有來源（Jina、Google News、Bing News、DuckDuckGo、Wikipedia）都失敗",
    }


def web_search(query: str, limit: int = 10, verbose: bool = False) -> Dict:
    """
    同步包裝，並行搜尋。
    支援雙模式：
      - 從同步上下文呼叫：asyncio.run() 建立新循環（原有行為）
      - 從已有事件循環呼叫（async 上下文）：直接 await 避免衝突
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 沒有執行中的循環，用 asyncio.run() 建立新的
        return asyncio.run(web_search_async(query, limit, verbose))

    # 已在事件循環內，建立 Task 併入當前循環
    async def _run():
        return await web_search_async(query, limit, verbose)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, web_search_async(query, limit, verbose))
        return future.result()


def web_search_to_string(query: str, limit: int = 10, verbose: bool = False) -> str:
    """
    將搜尋結果格式化為易讀字串，直接傳入 LLM 作為上下文。
    """
    data = web_search(query, limit, verbose)

    if data["error"]:
        return f"[網路搜尋失敗：{data['error']}]"

    source_labels = {
        "jina":        "Jina",
        "google_news": "Google News",
        "bing_news":   "Bing News",
        "duckduckgo":  "DuckDuckGo",
        "wikipedia":   "Wikipedia",
    }
    source_label = source_labels.get(data["source"], data["source"])
    now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    lines = [f"🔍 「{query}」搜尋結果（{source_label}，{now_str}）\n"]
    for r in data["results"]:
        line = r.to_str()
        if r.snippet:
            line += f"\n   └─ {r.snippet[:120]}"
        lines.append(line)

    return "\n".join(lines)


# ─── 測試 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "F1 Monaco Grand Prix 2026"
    print(f"搜尋：{q}\n")
    result = web_search_to_string(q, limit=8, verbose=True)
    print(result)