#!/usr/bin/env python3
"""
Hermes WebSocket Chat Bridge
WebSocket → Hermes REST API (streaming SSE)
避免瀏覽器 CORS 問題
智慧資訊推薦：偵測使用者興趣，主動拿相關新聞/文章推薦
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import websockets
import httpx
from datetime import datetime
from typing import Optional, Any
import threading
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# 多來源網路搜尋（Google News → Bing News → DuckDuckGo，自動降級）
from fallback_web_search import web_search_to_string as fallback_search_to_string
from fallback_web_search import web_search_async
from fallback_web_search import SearchResult

HERMES_HOST = os.getenv("HERMES_HOST", "127.0.0.1")
HERMES_PORT = int(os.getenv("HERMES_PORT", "8642"))
WS_PORT = int(os.getenv("WS_PORT", "8767"))
# Twelve-Factor: FastAPI 後端 URL 统一從環境變數讀取
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")

# ─── 搜尋觸發關鍵字（時間、搜尋）─────────────────────────────
# 偵測到以下任一關鍵字，立即執行網頁搜尋並預掛結果
SEARCH_TRIGGER_KEYWORDS = ["時間", "搜尋"]


# ─── 擴充版資訊意圖偵測（行程助理核心）─────────────────────────────

RECOMMEND_PATTERNS = [
    # ── 明確推薦意圖（原有）─────────────────
    r"有.*推薦", r"推薦.*", r"值得.*看", r"有.*值得",
    r"最近.*怎麼", r"最近.*發展", r"最近.*進展", r"最近.*動態",
    r"有.*新聞", r"有.*報導", r"有.*文章", r"想了解", r"想知",
    r"想看.*關於", r"給我.*關於", r"幫我找.*", r"有什麼.*推薦",
    r"有什麼新鮮事", r"最近有什麼",
    # ── 行程助理常見問法（大幅擴充）────────
    r"告訴我.*", r"介紹.*", r"請問", r"我想知道",
    r"什麼是", r"是什麼", r"怎麼樣", r"怎樣",
    r"何時", r"幾時", r"幾點", r"哪裡", r"在哪", r"地在哪",
    r"誰.*是", r"誰.*在", r"什麼.*時候", r"為什麼",
    r"有什麼.*活動", r"有.*比賽", r"有.*賽事",
    r"賽程", r"賽果", r"戰況", r"戰績",
    r"門票", r"票價", r"地點", r"位置",
    r"最新.*", r"最近.*活動", r"即時.*",
    r"天氣", r"氣溫", r"下雨", r"晴天",
    r"路況", r"交通", r"航班", r"火車",
    # ── 主題領域關鍵字（自動觸發搜尋）──────
    r"FIFA", r"世界盃", r"奧運", r"亞奧運", r"NBA", r"MLB", r"世界杯",
    r"演唱會", r"音樂節", r"展覽", r"活動", r"節日",
    r"春節", r"端午", r"中秋", r"跨年", r"新年",
    # ── 英文常見問法 ───────────────────────
    r"what is", r"what's", r"who is", r"who's", r"when is", r"where is",
    r"tell me about", r"what happened", r"what's happening",
    r"latest", r"schedule", r"results", r"score",
    r"can you tell me", r"i want to know", r"looking for",
]

# 需要主動搜尋的主題領域（，出現任一詞就觸發）
LIVE_INFO_TOPICS = [
    # 運動賽事
    "世界盃", "FIFA", "足球", "籃球", "NBA", "棒球", "MLB", "網球",
    "奧運", "亞運", "世界杯", "大賽", "賽事", "比賽", "季後賽", "總決賽",
    # 娛樂活動
    "演唱會", "音樂節", "展覽", "影展", "電影", "新片", "上映",
    "演唱", "歌手", "明星", "偶像",
    # 時事新聞
    "新聞", "時事", "最新", "頭條", "熱門",
    # 行程相關
    "行程", "活動", "會議", "約", "時間", "日程", "表訂",
    # 氣象交通
    "天氣", "氣象", "雨", "風", "溫度", "交通", "路況", "航班", "高鐵",
    # 英文關鍵字
    "news", "event", "match", "game", "concert", "festival", "schedule",
    "ticket", "weather", "result", "score", "live",
]

# 問句模式（問什麼/何時/哪裡/誰/為什麼 + 有意義主題詞）
QUESTION_PATTERNS = [
    r"告訴我.*[^\s]", r"請問.*[^\s]", r"我想知道.*[^\s]",
    r"什麼是.*[^\s]", r"什麼.*時候", r"什麼.*地點", r"什麼.*原因",
    r"何時.*[^\s]", r"幾時.*[^\s]", r"幾點.*[^\s]",
    r"在哪.*[^\s]", r"哪裡.*[^\s]", r"地在哪",
    r"誰.*[^\s]", r"為什麼.*[^\s]", r"怎麼.*[^\s]", r"怎樣.*[^\s]",
    # 英文問句
    r"what (is|are|was|were| happened| going)", r"when (is|are|was|does|did)",
    r"where (is|are|was|does)", r"who (is|are|was|does)",
    r"why (is|are|was|does|did)", r"how (do|does|did|to)",
]

# 應排除的單純對話（不該觸發搜尋）
CONVERSATION_PATTERNS = [
    r"^[\s]*你好", r"^[\s]*您好", r"^[\s]*早安", r"^[\s]*午安", r"^[\s]*晚安",
    r"^[\s]*hi[\s]*$", r"^[\s]*hey[\s]*$", r"^[\s]*hello[\s]*$",
    r"^[\s]*謝謝", r"^[\s]*感謝", r"^[\s]*再見", r"^[\s]*掰掰",
    r"^[\s]*沒錯", r"^[\s]*對", r"^[\s]*好的", r"^[\s]*好",
    r"^[\s]*可以", r"^[\s]*好啊",
]


def _has_live_topic(text: str) -> bool:
    """檢查是否提及需要即時資訊的主題"""
    t = text.lower()
    return any(kw.lower() in t for kw in LIVE_INFO_TOPICS)


def _is_question(text: str) -> bool:
    """檢查是否為問句"""
    for p in QUESTION_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    # 中文問句：結尾有問號
    if "？" in text or "?" in text:
        return True
    return False


def _is_simple_conversation(text: str) -> bool:
    """檢查是否為單純寒喧（不該浪費搜尋配額）"""
    stripped = text.strip()
    for p in CONVERSATION_PATTERNS:
        if re.search(p, stripped, re.IGNORECASE):
            return True
    # 真的太短（<4字）且無明確主題
    if len(stripped) < 4 and not _has_live_topic(stripped):
        return True
    return False


def detect_recommendation_intent(user_message: str) -> bool:
    """
    擴充版偵測：幾乎任何需要參考資料的問答都出發搜尋。
    觸發條件（符合任一）：
      1. 匹配 RECOMMEND_PATTERNS（明確推薦意圖）
      2. 包含 LIVE_INFO_TOPICS 關鍵字（行程助理核心場景）
      3. 同時滿足：問句 + 非純寒喧（動態資訊需求）
    排除：純寒喧、太短無意義句
    """
    text = user_message.strip()
    if not text:
        return False

    # 排除：純寒喧 / 問候 / 太短
    if _is_simple_conversation(text):
        return False

    # 條件1：匹配任一推薦/資訊 pattern
    for pattern in RECOMMEND_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    # 條件2：提到需要即時資訊的主題
    if _has_live_topic(text):
        return True

    # 條件3：問句 + 有實質內容（非純問候）
    if _is_question(text) and len(text) >= 6:
        return True

    return False


def extract_topic_keywords(user_message: str) -> str:
    """從使用者訊息中抽取感興趣的主題關鍵字（支援中英文混合）

    擴充版：同時參考 RECOMMEND_PATTERNS、LIVE_INFO_TOPICS、QUESTION_PATTERNS
    的關鍵字，優先取完整詞組而非單字。
    """
    text = user_message.strip()
    if not text:
        return ""

    keywords: list[str] = []

    # ── Step 1: 把所有 pattern 詞集合在一起，完整匹配 ──
    all_pattern_keywords: list[str] = [
        # 領域關鍵字 → 直接納入（取完整匹配）
        "世界盃", "世界杯", "FIFA", "奧運", "亞運", "NBA", "MLB",
        "演唱會", "音樂節", "展覽", "影展", "演唱", "偶像",
        "春節", "端午", "中秋", "跨年", "新年",
        "天氣", "氣象", "交通", "路況", "航班", "高鐵",
        # 賽事相關
        "賽程", "賽果", "戰況", "戰績", "門票", "票價",
        # 新聞/時事
        "頭條", "熱門",
    ]
    for kw in all_pattern_keywords:
        # 不分大小寫完整匹配
        if re.search(re.escape(kw), text, re.IGNORECASE):
            keywords.append(kw)

    # ── Step 2: 中文長詞 n-gram 提取（2-4 字）─────────────
    chinese_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
    stopword_chars = set(
        "的是在有和與了嗎呢吧啊我你他她它我們你們大家"
        "這那什麼怎麼為什麼如何哪哪些一下些一點個別人"
        "可以能會要我想覺得最近現在目前今天明天昨天情況"
        "消息進展最新推薦值得幫我給我想了解想知道請問有什麼沒"
    )
    for seq in chinese_seqs:
        if len(seq) > 3:
            ngrams = set()
            for n in range(2, 5):
                for i in range(len(seq) - n + 1):
                    ngrams.add(seq[i:i+n])
            for ng in sorted(ngrams, key=len, reverse=True):
                if len(ng) >= 2 and all(c not in stopword_chars for c in ng):
                    if ng not in keywords:
                        keywords.append(ng)
                    break
        elif len(seq) >= 2 and seq not in stopword_chars:
            if seq not in keywords:
                keywords.append(seq)

    # ── Step 3: 英文單字 ──────────────────────────────────
    english_words = re.findall(r'[a-zA-Z0-9]{2,}', text)
    en_stop = {"please", "can", "could", "would", "about", "what", "when",
               "where", "who", "why", "how", "this", "that", "these", "those",
               "tell", "want", "know", "looking", "find", "need", "latest",
               "search", "from", "have", "with", "for", "the", "and", "but"}
    for w in english_words:
        if w.lower() not in en_stop and w not in keywords:
            keywords.append(w)

    return " ".join(keywords[:6])


# ─── 通用爬網頁意圖偵測 ───

CRAWL_PATTERNS = [
    # 中文：問網頁內容、最近更新、特定網站
    r"幫我查.*網站", r"幫我看看.*網站", r"這個.*網站", r"那個.*網站",
    r"最近.*更新", r"最新.*動態", r"這個.*怎麼樣", r"那個.*怎麼樣",
    r"幫我上網查", r"幫我搜尋.*網頁", r"查一下.*", r"查看.*",
    r"請幫我查.*", r"幫我找.*資料", r"上網查.*",
    # 英文
    r"look up", r"check.*website", r"browse", r"crawl", r"fetch.*page",
    r"what's on.*site", r"get.*content",
]

CRAWL_STOPWORDS = {
    "的", "是", "在", "有", "和", "與", "了", "嗎", "呢", "吧", "啊",
    "我", "你", "他", "她", "它", "我們", "你們", "大家",
    "這", "那", "什麼", "怎麼", "為什麼", "如何", "哪", "哪些",
    "一下", "些", "一點", "個", "請問", "能", "會", "要", "可以",
    "最近", "現在", "目前", "今天", "明天", "昨天",
}


def detect_crawl_intent(user_message: str) -> bool:
    """偵測是否需要爬網頁（給定 URL 或可抽取關鍵字）"""
    for pattern in CRAWL_PATTERNS:
        if re.search(pattern, user_message, re.IGNORECASE):
            return True
    return False


def extract_crawl_keywords(user_message: str) -> str:
    """從訊息中抽取可當作搜尋關鍵字的詞"""
    text = re.sub(r'[^\w\s]', ' ', user_message)
    chinese_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
    english_words = re.findall(r'[a-zA-Z0-9]+', text)

    keywords = []
    for seq in chinese_seqs:
        if seq not in CRAWL_STOPWORDS:
            keywords.append(seq)
    for w in english_words:
        if w.lower() not in CRAWL_STOPWORDS and len(w) > 1:
            keywords.append(w)

    return " ".join(keywords[:5])


# ─── 搜尋觸發意圖偵測（時間、搜尋關鍵字）──────────────────────

def detect_search_trigger_intent(user_message: str) -> bool:
    """偵測「時間」「搜尋」等關鍵字，滿足則立即觸發網頁搜尋"""
    return any(kw in user_message for kw in SEARCH_TRIGGER_KEYWORDS)


def extract_search_keywords(user_message: str) -> str:
    """從使用者訊息中抽取搜尋關鍵字（移除干擾詞）"""
    text = user_message.strip()
    # 移除常見寒暄與問句結尾
    text = re.sub(r'[？?。.！!]$', '', text)
    text = re.sub(r'^(請問|我想知道|告訴我|幫我查|幫我找|查詢|搜尋)[\s：:]*', '', text)

    # 移除時間/搜尋本身（觸發詞不算關鍵字）
    text = text.replace("時間", "").replace("搜尋", "")

    # 清理殘留的停用字
    stopwords = ["一下", "一些", "這個", "那個", "什麼", "怎樣", "如何",
                 "可以", "能夠", "需要", "想", "要", "的", "是", "了",
                 "有", "沒有", "嗎", "呢", "吧", "啊"]
    for sw in stopwords:
        text = text.replace(sw, " ")

    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) >= 2 else ""


# ─── 爬蟲（透過 FastAPI 後端）───

def crawl_via_api(keywords: str) -> str:
    """呼叫 FastAPI /api/crawl 拿網頁內容（嘗試 DuckDuckGo API → 維基百科 API）"""
    if not keywords.strip():
        return ""

    import requests as req
    target_url = None

    # ── 嘗試 1: DuckDuckGo JSON API ──
    try:
        api_url = f"https://api.duckduckgo.com/?q={quote(keywords)}&format=json&no_redirect=1&t=hermes"
        headers = {"User-Agent": "HermesBot/1.0"}
        resp = req.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # 從 RelatedTopics 找第一個外部 URL
            for topic in data.get("RelatedTopics", []):
                url = topic.get("FirstURL", "")
                if url and url.startswith("http"):
                    target_url = url
                    break
            # 備用：AbstractText/AbstractURL（維基百科之類的摘要）
            if not target_url:
                abstract_url = data.get("AbstractURL", "")
                if abstract_url:
                    target_url = abstract_url
    except Exception:
        pass

    # ── 嘗試 2: Bing News RSS ──
    if not target_url:
        try:
            import re as re2
            rss_url = f"https://www.bing.com/news/search?q={quote(keywords)}&format=rss"
            headers2 = {"User-Agent": "Mozilla/5.0 (compatible; HermesBot/1.0)"}
            resp2 = req.get(rss_url, headers=headers2, timeout=10)
            if resp2.status_code == 200:
                items = re2.findall(r'<url>(https?://[^<]+)</url>', resp2.text)
                for item_url in items[:5]:
                    if item_url and not any(x in item_url for x in ["bing.com", "microsoft.com"]):
                        target_url = item_url[:500]
                        break
        except Exception:
            pass

    # ── 嘗試 3: Wikipedia API ──
    if not target_url:
        try:
            # 先嘗試英文維基
            wiki_api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(keywords.split()[0])}"
            headers3 = {"User-Agent": "HermesBot/1.0 (contact: hermes@example.com)"}
            resp3 = req.get(wiki_api, headers=headers3, timeout=8)
            if resp3.status_code == 200:
                data3 = resp3.json()
                if data3.get("content_urls", {}).get("desktop", {}).get("page"):
                    target_url = data3["content_urls"]["desktop"]["page"]
        except Exception:
            pass

    if not target_url:
        return ""

    # ── 用 FastAPI /api/crawl 爬取目標頁面 ──
    try:
        crawl_resp = req.post(
            f"{FASTAPI_URL}/api/crawl",
            json={"url": target_url, "max_links": 5},
            timeout=20
        )
        if crawl_resp.status_code == 200:
            data = crawl_resp.json()
            if data.get("error"):
                return ""
            if data.get("content") and data.get("title"):
                title = data["title"]
                content = data["content"][:800]
                return f"📄 爬取結果（「{title}」）\n\n{content}\n\n來源：{target_url}"
    except Exception:
        pass
    return ""


# ─── Playwright 通用爬蟲 ─────────────────────────────────────────────

BROWSER_PATH = "/snap/chromium/3459/usr/lib/chromium-browser/chrome"


def crawl_with_playwright(url: str, timeout: int = 15000) -> str:
    """用系統 chromium 無頭模式爬取任意 URL，回傳純文字"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=BROWSER_PATH,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = browser.new_page()
            page.goto(url, timeout=timeout)
            # 等 JS 渲染完成
            page.wait_for_load_state("networkidle", timeout=timeout)
            text = page.inner_text("body")
            browser.close()
            return text.strip()[:3000] if text else ""
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════
# ─── Browser Automation (Headless Chrome + Anti-Bot Evasion) ──────────
# 用途：Firecrawl 失效時的瀏覽器級備援，可繞過 JS 挑戰、驗證碼等
# 實作：
#   1. Selenium + 系統 Chromium，CDP 原生指令注入 anti-bot 腳本
#   2. BrowserManager singleton 維護長期瀏覽器程序（避免重啟開銷）
#   3. Anti-bot Evasion：移除 webdriver 指紋、模擬正常瀏覽器屬性
# 參考工具：undetected-chromedriver, selenium-stealth, cloudscraper
# ═══════════════════════════════════════════════════════════════════════

BROWSER_AUTOMATION_ENABLED = os.getenv("BROWSER_AUTOMATION_ENABLED", "false").lower() == "true"


class BrowserManager:
    """
    Selenium Headless Chrome 單例，懶惰初始化。
    收到第一個 request 才啟動程序，之後複用。
    """

    _instance: Optional["BrowserManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.driver: Optional[Any] = None  # Selenium WebDriver
        self._alive = False

    @classmethod
    def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Anti-Bot 注入腳本（CDP evaluate before page load）─────────
    ANTI_BOT_SCRIPT = """
    // 移除 Selenium/WebDriver 指紋
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // 模擬正常外掛列表
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // 模擬語言
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-TW', 'zh', 'en-US', 'en']
    });

    // 模擬硬體並行
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8
    });

    // 模擬裝置記憶體
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8
    });

    // 移除 automation 標記
    window.chrome = { runtime: {} };

    // Toy: 模擬 canvas 指紋隨機性
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attrs) {
        return origGetContext.call(this, type, attrs);
    };
    """

    def start(self) -> bool:
        """啟動 headless Chrome 程序（只執行一次）"""
        if self._alive and self.driver is not None:
            try:
                self.driver.current_url  # 測試連線
                return True
            except Exception:
                self._alive = False

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.binary_location = BROWSER_PATH
            opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--no-first-bot-open")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--disable-infobars")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 "
                              "Safari/537.36")

            service = Service(executable_path=BROWSER_PATH, port=9222)
            self.driver = webdriver.Chrome(service=service, options=opts)

            # CDP：注入 anti-bot 腳本到所有新文件
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": self.ANTI_BOT_SCRIPT}
            )

            self._alive = True
            print(f"[BrowserManager] Headless Chrome 已啟動（PID: {service.process.pid}）", flush=True)
            return True

        except Exception as e:
            print(f"[BrowserManager] 啟動失敗: {e}", flush=True)
            self._alive = False
            return False

    def crawl(self, url: str, timeout: int = 15000) -> str:
        """
        用 headless Chrome 訪問 URL，回傳純文字（最多 3000 字）。
        失敗時回傳空字串，由呼叫端決定降級處理。
        """
        if not self.start():
            return ""

        try:
            self.driver.get(url)
            # 等 DOM 載入
            self.driver.implicitly_wait(timeout / 2000)  # selenium 用秒
            # 再等網路空閒（額外 5s）
            time.sleep(5)
            text = self.driver.find_element("tag name", "body").text
            return text.strip()[:3000] if text else ""
        except Exception as e:
            print(f"[BrowserManager] 抓取失敗 {url}: {e}", flush=True)
            # 重置瀏覽器狀態
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self._alive = False
            return ""

    def close(self):
        """關閉瀏覽器程序（供外部呼叫）"""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        finally:
            self.driver = None
            self._alive = False


def crawl_with_headless_chrome(url: str, timeout: int = 15000) -> str:
    """
    公開介面：使用 Selenium Headless Chrome 抓取任意 URL。
    - 自動維護單一瀏覽器程序（BrowserManager singleton）
    - 注入 anti-bot 腳本繞過基礎偵測
    - 回傳純文字（最長 3000 字），失敗回傳空字串
    """
    if not BROWSER_AUTOMATION_ENABLED:
        return ""

    manager = BrowserManager.get_instance()
    return manager.crawl(url, timeout=timeout)


# ─── 新聞推薦：多來源降級搜尋 ───────────────────────────────────

async def fetch_news_for_topic(keywords: str) -> str:
    """用 fallback_web_search 多來源降級拿新聞（Google → Bing → DuckDuckGo）
       全部失敗時則嘗試直接 crawl python.org 下載頁面"""
    if not keywords.strip():
        return ""

    print(f"[fetch_news_for_topic] 開始搜尋，關鍵字={keywords}", flush=True)
    data = await web_search_async(keywords, limit=12, verbose=False)
    print(f"[fetch_news_for_topic] web_search_async 完成，source={data.get('source')}, results={len(data.get('results',[]))}, error={data.get('error')}", flush=True)

    # 新聞 API 成功
    if not data.get("error") and data.get("results"):
        source_labels = {
            "jina":        "Jina",
            "google_news": "Google News",
            "bing_news":   "Bing News",
            "duckduckgo":  "DuckDuckGo",
            "wikipedia":   "Wikipedia",
        }
        source_label = source_labels.get(data["source"], data["source"])
        now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        lines = [f"🔍 「{keywords}」搜尋結果（{source_label}，{now_str}）\n"]
        for r in data.get("results", []):
            line = r.to_str()
            if r.snippet:
                line += f"\n   └─ {r.snippet[:120]}"
            lines.append(line)
        return "\n".join(lines)

    # 新聞來源全部失敗 → fallback：先用 Headless Chrome 爬 news.google.com
    if BROWSER_AUTOMATION_ENABLED:
        try:
            news_url = f"https://news.google.com/search?q={quote(keywords)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            content = crawl_with_headless_chrome(news_url, timeout=15000)
            if content and len(content) > 100:
                lines = content.split("\n")
                meaningful = [l.strip() for l in lines if len(l.strip()) > 15][:25]
                if meaningful:
                    return (
                        f"🔍 「{keywords}」（Headless Chrome，{datetime.now().strftime('%Y年%m月%d日 %H:%M')}）\n\n"
                        + "\n".join(f"• {l}" for l in meaningful)
                        + f"\n\n來源：{news_url}"
                    )
        except Exception:
            pass

    # 最後 fallback：Playwright 爬 news.google.com（需系統 Chromium）
    try:
        news_url = f"https://news.google.com/search?q={quote(keywords)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        content = crawl_with_playwright(news_url, timeout=15000)
        if content and len(content) > 100:
            lines = content.split("\n")
            meaningful = [l.strip() for l in lines if len(l.strip()) > 15][:25]
            if meaningful:
                return (
                    f"🔍 「{keywords}」（News 爬蟲，{datetime.now().strftime('%Y年%m月%d日 %H:%M')}）\n\n"
                    + "\n".join(f"• {l}" for l in meaningful)
                    + f"\n\n來源：{news_url}"
                )
    except Exception:
        pass

    # 最後 fallback：python.org 下載頁面
    topic_lower = keywords.lower()
    if "python" in topic_lower or "py" in topic_lower:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{FASTAPI_URL}/api/crawl",
                    json={"url": "https://www.python.org/downloads/", "max_links": 3}
                )
                if resp.status_code == 200:
                    result = resp.json()
                    content = result.get("content", "")
                    if content and len(content) > 50:
                        return (
                            f"📦 Python 官網下載頁面（直接抓取）\n\n"
                            f"{content[:600]}\n\n"
                            f"來源：https://www.python.org/downloads/"
                        )
        except Exception:
            pass

    return f"[網路搜尋失敗：所有來源（Google News、Bing News、DuckDuckGo、Wikipedia、Playwright）都失敗]"


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
    """呼叫 Hermes REST non-streaming，回傳完整回應。429 時自動重試（最多 3 次）。"""
    hermes_payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(4):
            try:
                resp = await client.post(
                    f"http://{HERMES_HOST}:{HERMES_PORT}/v1/chat/completions",
                    json=hermes_payload,
                    headers=headers,
                )
            except Exception as e:
                return json.dumps({"error": str(e)})

            if resp.status_code == 200:
                data = resp.json()
                # 檢查 Hermes 內部是否還有 error（例如 429 重試完仍失敗）
                hermes_meta = data.get("hermes", {})
                if hermes_meta.get("error") and "429" in str(hermes_meta.get("error", "")):
                    # Hermes 報 429，等 5 秒後重試
                    if attempt < 3:
                        wait = 5 * (attempt + 1)
                        print(f"[Retry] Hermes 429，等 {wait}s 後重試 (attempt {attempt+1}/3)", flush=True)
                        time.sleep(wait)
                        continue
                    else:
                        return json.dumps({"error": hermes_meta.get("error")})

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return json.dumps({"content": content})

            elif resp.status_code == 429:
                # Rate limit，等 5 秒後重試
                if attempt < 3:
                    wait = 5 * (attempt + 1)
                    print(f"[Retry] HTTP 429，等 {wait}s 後重試 (attempt {attempt+1}/3)", flush=True)
                    time.sleep(wait)
                    continue
                else:
                    return json.dumps({"error": f"HTTP 429 after 3 retries"})

            else:
                return json.dumps({"error": f"HTTP {resp.status_code}: {resp.text}"})

        return json.dumps({"error": "Max retries exhausted"})


async def _quick_search(query: str, limit: int = 8, timeout: float = 3.0) -> str:
    """
    非同步快速搜尋：直接 await web_search_async，並在 timeout 秒後強制放棄。
    這樣不會像同步版本那样阻塞事件循環。
    失敗時回傳 "[網路搜尋失敗]"（短訊息，不inject system message）。
    """
    try:
        result = await asyncio.wait_for(
            web_search_async(query, limit, verbose=False),
            timeout=timeout
        )
        if result.get("error") or not result.get("results"):
            # 失敗時回傳提示，讓 LLM 自己判斷
            return ""
        # 格式化為字串
        from fallback_web_search import web_search_to_string
        return web_search_to_string(query, limit, verbose=False)
    except asyncio.TimeoutError:
        print(f"[_quick_search] 逾時（{timeout}s），放棄搜尋", flush=True)
        return ""
    except Exception as e:
        print(f"[_quick_search] 錯誤：{e}", flush=True)
        return ""


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

            # ── 搜尋觸發偵測（時間、搜尋關鍵字）───
            if detect_search_trigger_intent(user_text):
                search_kw = extract_search_keywords(user_text)
                if search_kw:
                    print(f"[SearchTrigger] 偵測到搜尋關鍵字：「{search_kw}」")
                    # 用 async 版本 + 3s 逾時，避免阻塞事件循環
                    search_result = await _quick_search(search_kw, limit=8)
                    if search_result and len(search_result) >= 20:
                        print(f"[SearchTrigger] 拿到搜尋結果，長度: {len(search_result)} 字")
                        search_msg = {
                            "role": "system",
                            "content": (
                                f"【系統主動搜尋結果，請直接參考以下資料回答】\n\n"
                                f"{search_result}\n\n"
                                f"請根據以上搜尋結果回答用戶問題，無需再呼叫搜尋工具。"
                            )
                        }
                        messages = [search_msg] + messages
                    else:
                        print("[SearchTrigger] 搜尋無結果或太短，跳過")

            # ── 爬蟲意圖偵測 ──
            if detect_crawl_intent(user_text):
                crawl_kw = extract_crawl_keywords(user_text)
                if crawl_kw:
                    print(f"[Crawl] 偵測到爬蟲意圖，關鍵字:「{crawl_kw}」")
                    crawl_data = crawl_via_api(crawl_kw)
                    if crawl_data:
                        print(f"[Crawl] 拿到內容，長度: {len(crawl_data)} 字")
                        context_msg = {
                            "role": "system",
                            "content": (
                                f"【以下是你可以使用的參考資料，不需要再呼叫搜尋工具】\n\n"
                                f"{crawl_data}\n\n"
                                f"請根據以上資料回答用戶問題。如果資料不足或無法回答，請說明並建議用戶提供更多細節。"
                            )
                        }
                        messages = [context_msg] + messages

            result = await bridge_to_hermes(messages, model)

            # ── Tool Call 迴圈：攔截搜尋工具，改用 fallback_web_search ──
            for _ in range(10):  # 最多 10 層tool call，防止無限循環
                result_data = json.loads(result)
                if "error" in result_data:
                    break

                msg_content = result_data.get("choices", [{}])[0].get("message", {})
                tool_calls = msg_content.get("tool_calls", [])

                if not tool_calls:
                    # 沒有 tool_calls，直接回覆
                    break

                # 找搜尋相關的 tool_call，用 fallback_web_search 取代
                search_calls = [tc for tc in tool_calls
                                if tc.get("function", {}).get("name", "").lower()
                                in ("web_search", "search", "fallback_web_search", "firecrawl_search")]
                if not search_calls:
                    # 有 tool_calls 但非搜尋相關，照正常流程走（LLM 自行處理）
                    break

                print(f"[Fallback] 攔截到 {len(search_calls)} 個搜尋 tool_call", flush=True)

                for tc in search_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args = fn.get("arguments", "{}")
                    if isinstance(fn_args, str):
                        fn_args = json.loads(fn_args)

                    # 取出搜尋關鍵字
                    query = fn_args.get("query") or fn_args.get("search") or fn_args.get("keywords", "")
                    if not query:
                        query = fn_args.get("q", "")

                    if query:
                        print(f"[Fallback] 執行降級搜尋，關鍵字:「{query}」", flush=True)
                        # 用 async 版本，3s 逾時，避免阻塞
                        search_result = await _quick_search(query, limit=8, timeout=3.0)
                        if not search_result or len(search_result) < 20:
                            search_result = "（降級搜尋無結果，請說明無法找到相關資訊）"
                    else:
                        search_result = "（無法取出搜尋關鍵字）"

                    # 把 tool 結果加回 messages
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", tc.get("tool_call_id", "unknown")),
                        "content": search_result,
                    })
                    print(f"[Fallback] 搜尋結果長度: {len(search_result)} 字", flush=True)

                # 下一輪：送更新後的 messages 給 Hermes
                result = await bridge_to_hermes(messages, model)

            # ── 最終回覆回傳前端 ──
            try:
                final_data = json.loads(result)
                if "error" in final_data:
                    await websocket.send(json.dumps({"error": final_data["error"]}))
                else:
                    final_content = final_data.get("content", "")
                    if not final_content:
                        # 有 tool_calls 但被拦截完了，取最後一個 assistant message
                        final_content = final_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    await websocket.send(json.dumps({
                        "type": "chunk",
                        "content": final_content,
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