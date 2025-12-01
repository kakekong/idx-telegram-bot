import os, json, time, datetime, requests, sqlite3
from playwright.sync_api import sync_playwright
from telebot import TeleBot

TOKEN   = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TV_USER = os.getenv("TV_USER")
TV_PASS = os.getenv("TV_PASS")
EXCHG   = os.getenv("EXCHANGE") or "IDX"

WIB   = datetime.timezone(datetime.timedelta(hours=7))
BOT   = TeleBot(TOKEN)

# ---------- market helpers ----------
def _is_trading_day():
    today = datetime.datetime.now(WIB).date()
    if today.weekday() >= 5:
        return False
    holidays = {2025: [(1,1), (2,28), (5,1), (6,1), (6,19), (8,17), (12,25)]}
    return (today.month, today.day) not in holidays.get(today.year, [])

def _market_hours():
    now = datetime.datetime.now(WIB).time()
    return datetime.time(9, 0) <= now <= datetime.time(15, 0)

# ---------- notify open/close once per day ----------
_last_open_notif = _last_close_notif = None

def _notify_once_open():
    global _last_open_notif
    today = datetime.datetime.now(WIB).date()
    if today != _last_open_notif:
        BOT.send_message(CHAT_ID, "🟢 IDX market opened – 15-min breakout scan started.")
        _last_open_notif = today

def _notify_once_close():
    global _last_close_notif
    today = datetime.datetime.now(WIB).date()
    if today != _last_close_notif:
        BOT.send_message(CHAT_ID, "🔴 IDX market closed – scan stopped.")
        _last_close_notif = today

# ---------- browser ----------
def _new_page():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.tradingview.com/accounts/signin/")
    page.fill('[name="username"]', TV_USER)
    page.fill('[name="password"]', TV_PASS)
    page.click('button[type="submit"]')
    page.wait_for_url("https://www.tradingview.com/**", timeout=30000)
    return browser, page

# ---------- free 15-min scan ----------
def scan_one(ticker: str) -> bool:
    if not (_is_trading_day() and _market_hours()):
        return False
    browser, page = _new_page()
    try:
        page.goto(f"https://www.tradingview.com/symbols/{EXCHG}-{ticker}/?interval=15")
        page.wait_for_load_state("networkidle")
        vol, avg = page.evaluate("""() => {
            const chart = tvWidget.activeChart;
            const bars = chart.series.bars().bars;
            const ind  = chart.getAllStudies().find(s=>s.name.includes("Breakout Volume"));
            if (!bars.length || !ind) return [0,0];
            return [bars[bars.length-1].volume, chart.getStudyById(ind.id).outputs.avg_vol];
        }""")
    except Exception:
        vol, avg = 0, 0
    finally:
        browser.close()
    return vol >= 1.5 * avg if avg else False

# ---------- 15-min scheduler ----------
def run_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    sched = BlockingScheduler()

    @sched.scheduled_job('cron', hour=9, minute=0, second=0, timezone=WIB)
    def open_msg():
        if _is_trading_day():
            _notify_once_open()

    @sched.scheduled_job('cron', hour=15, minute=0, second=5, timezone=WIB)
    def close_msg():
        if _is_trading_day():
            _notify_once_close()

    @sched.scheduled_job('cron', minute='*/15', second=0, timezone=WIB)
    def scan_job():
        if not (_is_trading_day() and _market_hours()):
            return
        conn = sqlite3.connect("alerts.db", check_same_thread=False)
        for (ticker,) in conn.execute("SELECT ticker FROM alerts").fetchall():
            if scan_one(ticker):
                BOT.send_message(CHAT_ID, f"🔊 15-min volume breakout!\nSymbol: {ticker}")
        conn.close()

    sched.start()

# ---------- stubs ----------
def create_alert(ticker: str, webhook_url: str) -> str:
    conn = sqlite3.connect("alerts.db", check_same_thread=False)
    conn.execute("INSERT OR IGNORE INTO alerts(ticker) VALUES (?)", (ticker,))
    conn.commit(); conn.close()
    return f"scan-{ticker}"

def delete_alert(aid: str):
    ticker = aid.replace("scan-", "")
    conn = sqlite3.connect("alerts.db", check_same_thread=False)
    conn.execute("DELETE FROM alerts WHERE ticker=?", (ticker,))
    conn.commit(); conn.close()
