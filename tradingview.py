import os, json, time, datetime, requests, sqlite3
from playwright.sync_api import sync_playwright
from telebot import TeleBot

TV_USER  = os.getenv("TV_USER")
TV_PASS  = os.getenv("TV_PASS")
EXCHANGE = os.getenv("EXCHANGE") or "IDX"
TOKEN    = os.getenv("TOKEN")
CHAT_ID  = os.getenv("CHAT_ID")
BOT      = TeleBot(TOKEN)

WIB = datetime.timezone(datetime.timedelta(hours=7))

# ---------- same holiday helper ----------
def _is_trading_day():
    today = datetime.datetime.now(WIB).date()
    if today.weekday() >= 5:
        return False
    holidays = {2025: [(1,1), (2,28), (5,1), (6,1), (6,19), (8,17), (12,25)]}
    return (today.month, today.day) not in holidays.get(today.year, [])

def _market_hours():
    now = datetime.datetime.now(WIB).time()
    return datetime.time(9,0) <= now <= datetime.time(15,0)

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

# ---------- single ticker scan ----------
def scan_one(ticker: str) -> bool:
    """Returns True if last 15-m candle volume ≥ 1.5× avg."""
    if not (_is_trading_day() and _market_hours()):
        return False
    browser, page = _new_page()
    try:
        page.goto(f"https://www.tradingview.com/symbols/{EXCHANGE}-{ticker}/?interval=15")
        page.wait_for_load_state("networkidle")
        # grab last candle volume & 10-bar average from indicator
        vol, avg = page.evaluate("""() => {
            const chart = tvWidget.activeChart;
            const bars   = chart.series.bars().bars;
            const ind    = chart.getStudyById(
                chart.getAllStudies().find(s=>s.name.includes("Breakout Volume")).id
            );
            const vol = bars[bars.length-1].volume;
            const avg = ind.outputs.avg_vol;
            return [vol, avg];
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
    @sched.scheduled_job('cron', minute='*/15', second=0)
    def job():
        conn = sqlite3.connect("alerts.db", check_same_thread=False)
        for (ticker,) in conn.execute("SELECT ticker FROM alerts").fetchall():
            if scan_one(ticker):
                BOT.send_message(CHAT_ID, f"🔊 Breakout volume 15-menit!\nSimbol: {ticker}")
        conn.close()
    sched.start()

# ---------- stub functions (so old bot logic still compiles) ----------
def create_alert(ticker: str, webhook_url: str) -> str:
    """We no longer create TV alerts; just insert into local DB."""
    conn = sqlite3.connect("alerts.db", check_same_thread=False)
    conn.execute("INSERT OR IGNORE INTO alerts(ticker) VALUES (?)", (ticker,))
    conn.commit()
    conn.close()
    return f"scan-{ticker}"

def delete_alert(aid: str):
    ticker = aid.replace("scan-", "")
    conn = sqlite3.connect("alerts.db", check_same_thread=False)
    conn.execute("DELETE FROM alerts WHERE ticker=?", (ticker,))
    conn.commit()
    conn.close()
