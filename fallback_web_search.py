#!/usr/bin/env python3
"""
fallback_web_search.py
多來源網路搜尋：依序嘗試各免費來源，任一成功即回傳，完全失敗才回報錯誤。
來源順序：Google News RSS → Bing News RSS → DuckDuckGo HTML

用途：
  - ws_chat_bridge.py 的智慧推薦功能
  - 或作為 Hermes Agent 的独立工具
"""
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, urlencode
from typing import List, Dict, Optional

# ─── 統一結果格式 ────────────────────────────────────────────────

# ─── Source 4：Wikipedia 快速搜尋（curl + grep 關鍵字） ───────────

def search_wikipedia(query: str, limit: int = 5) -> Optional[List[SearchResult]]:
    """
    用 curl 直接 GET Wikipedia 頁面，以關鍵字快速過濾感興趣的段落。
    適用於：「甚麼是 XXX」、「XXX 的歷史」、「XXX 發明者/創辦人/時間」等問題。
    """
    try:
        encoded = quote(query)
        # 1. 用 OpenSearch API 取得相符的條目標題
        search_url = (
            f"https://en.wikipedia.org/w/api.php"
            f"?action=opensearch&search={encoded}&limit=3&format=json"
        )
        search_result = subprocess.run(
            ["curl", "-s", "--max-time", "8", search_url],
            capture_output=True, text=True
        )
        try:
            suggestions = json.loads(search_result.stdout)
            titles = suggestions[1] if len(suggestions) > 1 else []
        except Exception:
            titles = []

        if not titles:
            return None

        results = []
        for title in titles[:2]:
            article_url = f"https://en.wikipedia.org/wiki/{quote(title)}"

            # 2. curl 抓取 HTML，用 Python 過濾含關鍵字的 <p> 段落
            page_result = subprocess.run(
                ["curl", "-s", "--max-time", "10", "-L", article_url],
                capture_output=True, text=True
            )
            html = page_result.stdout
            if len(html) < 500:
                continue

            # 抽出所有 <p> 並去除 HTML 標籤
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
            matched = []
            for para in paragraphs[:20]:
                text = re.sub(r'<[^>]+>', '', para).strip()
                text = re.sub(r'\[.*?\]', '', text)
                if len(text) > 40 and query.lower() in text.lower():
                    matched.append(text)
                if len(matched) >= limit:
                    break

            # 3. 若關鍵字沒配到，直接用前3段當摘要
            if not matched:
                for para in paragraphs[:3]:
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
                results.append(SearchResult(
                    title=title,
                    url=article_url,
                    snippet=snippet,
                    source="Wikipedia",
                ))
                if len(results) >= 1:
                    break

        return results if results else None

    except Exception:
        return None


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

# ─── Source 1：Google News RSS（最快、最準） ───────────────────────

def search_google_news(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 Google News RSS 搜尋，支援中英文"""
    try:
        encoded = quote(query)
        # 英文介面拿到更多國際新聞
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}&hl=en&gl=US&ceid=US:en"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "12", "-L", rss_url],
            capture_output=True, text=True
        )
        xml_text = result.stdout
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
            # 清理 Google News 重新導向 URL
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


# ─── Source 2：DuckDuckGo HTML（無需 API Key） ─────────────────────

def search_duckduckgo(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 DuckDuckGo HTML 頁面截圖新聞區塊"""
    try:
        encoded = quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}+news"
        result = subprocess.run(
            ["curl", "-s", "--max-time", "12",
             "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
             url],
            capture_output=True, text=True
        )
        html = result.stdout
        if not html or "<html>" not in html.lower():
            return None

        results = []
        # DuckDuckGo HTML 結果格式
        for result_div in re.finditer(r'<a class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
            link = result_div.group(1).strip()
            title_html = result_div.group(2)
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and len(title) > 5:
                results.append(SearchResult(title=title, url=link))
            if len(results) >= limit:
                break

        # 沒有正則匹配時嘗試另一種格式
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


# ─── Source 3：Bing News RSS ──────────────────────────────────────

def search_bing_news(query: str, limit: int = 10) -> Optional[List[SearchResult]]:
    """用 Bing News RSS 搜尋"""
    try:
        encoded = quote(query)
        rss_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"
        result = subprocess.run(
            ["curl", "-s", "--max-time", "12", "-L", rss_url],
            capture_output=True, text=True
        )
        xml_text = result.stdout
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

            # 清理 CDATA
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


# ─── 主程式：多來源降級搜尋 ───────────────────────────────────────

def web_search(query: str, limit: int = 10, verbose: bool = False) -> Dict:
    """
    多來源依序搜尋，任一成功就回傳。

    參數：
        query  - 搜尋關鍵字
        limit  - 最多回傳結果數（預設 10）
        verbose - 顯示嘗試了哪些來源

    回傳：
        {
            "source": "google_news" | "bing_news" | "duckduckgo" | "none",
            "results": [SearchResult, ...],
            "error": None | "所有來源都失敗"
        }
    """
    sources = [
        ("google_news", search_google_news),
        ("bing_news",    search_bing_news),
        ("duckduckgo",   search_duckduckgo),
        ("wikipedia",    search_wikipedia),
    ]

    for name, fn in sources:
        if verbose:
            print(f"[fallback_search] 嘗試：{name}", flush=True)

        results = fn(query, limit)
        if results:
            if verbose:
                print(f"[fallback_search] 成功：{name}，拿到 {len(results)} 筆", flush=True)
            return {
                "source": name,
                "results": results,
                "error": None,
            }

    return {
        "source": "none",
        "results": [],
        "error": "所有來源（Google News、Bing News、DuckDuckGo）都失敗",
    }


def web_search_to_string(query: str, limit: int = 10, verbose: bool = False) -> str:
    """
    將搜尋結果格式化為易讀字串，直接傳入 LLM 作為上下文。
    """
    data = web_search(query, limit, verbose)

    if data["error"]:
        return f"[網路搜尋失敗：{data['error']}]"

    source_labels = {
        "google_news": "Google News",
        "bing_news": "Bing News",
        "duckduckgo": "DuckDuckGo",
        "wikipedia": "Wikipedia",
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