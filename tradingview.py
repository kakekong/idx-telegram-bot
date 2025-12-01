import os, datetime, sqlite3
from playwright.sync_api import sync_playwright
from telebot import TeleBot

# -------- ENV --------
TOKEN   = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TV_USER = os.getenv("TV_USER")
TV_PASS = os.getenv("TV_PASS")
EXCHG   = os.getenv("EXCHANGE") or "IDX"

BOT = TeleBot(TOKEN)
WIB = datetime.timezone(datetime.timedelta(hours=7))

# ----------------------------------------------------
# MARKET HELPER FUNCTIONS
# ----------------------------------------------------
def _is_trading_day():
    today = datetime.datetime.now(WIB).date()

    if today.weekday() >= 5:   # Sat / Sun
        return False

    holidays = {
        2025: [
            (1,1),(2,28),(5,1),(6,1),(6,19),(8,17),(12,25)
        ]
    }
    return (today.month, today.day) not in holidays.get(today.year, [])


def _market_hours():
    now = datetime.datetime.now(WIB).time()
    return datetime.time(9, 0) <= now <= datetime.time(15, 0)


# ----------------------------------------------------
# NOTIFY OPEN/CLOSE (ONCE)
# ----------------------------------------------------
_last_open_notif  = None
_last_close_notif = None

def _notify_once_open():
    global _last_open_notif
    today = datetime.datetime.now(WIB).date()
    if today != _last_open_notif:
        BOT.send_message(CHAT_ID, "🟢 IDX market opened — 15-min scan started.")
        _last_open_notif = today

def _notify_once_close():
    global _last_close_notif
    today = datetime.datetime.now(WIB).date()
    if today != _last_close_notif:
        BOT.send_message(CHAT_ID, "🔴 IDX market closed — scanner off.")
        _last_close_notif = today


# ----------------------------------------------------
# LOGIN + PAGE CREATION
# ----------------------------------------------------
def _new_page():
    pw = sync_playwright().start()
    # Use full chrome for stability
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-gpu", "--disable-dev-shm-usage"]
    )
    page = browser.new_page()

    # Login
    page.goto("https://www.tradingview.com/accounts/signin/")
    page.fill('[name="username"]', TV_USER)
    page.fill('[name="password"]', TV_PASS)
    page.click('button[type="submit"]')

    page.wait_for_url("https://www.tradingview.com/**", timeout=35000)
    return browser, page


# ----------------------------------------------------
# CHECK BREAKOUT OF ONE TICKER
# ----------------------------------------------------
def scan_one(ticker: str) -> bool:
    """
    Returns True if 15-min volume breakout (>=150% avg volume)
    """
    if not (_is_trading_day() and _market_hours()):
        return False

    browser, page = _new_page()

    try:
        page.goto(f"https://www.tradingview.com/symbols/{EXCHG}-{ticker}/?interval=15")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""
            () => {
                try {
                    const chart = tvWidget.activeChart();
                    if (!chart) return [0,0];

                    const series = chart.getSeries().mainSeries();
                    const bars = series._data._items;

                    if (!bars || bars.length < 2)
                        return [0,0];

                    const studies = chart.getAllStudies();
                    const breakout = studies.find(s => s.name.includes("Breakout Volume"));
                    if (!breakout) return [0,0];

                    const study = chart.getStudyById(breakout.id);
                    return [
                        bars[bars.length - 1].value[1],  // volume
                        study.outputs.avg_vol            // moving avg volume
                    ];
                } catch(e) {
                    return [0,0];
                }
            }
        """)

        vol, avg = result
    except Exception:
        vol, avg = 0, 0
    finally:
        browser.close()

    if not avg:
        return False

    return vol >= 1.5 * avg


# ----------------------------------------------------
# 15-MIN SCHEDULER
# ----------------------------------------------------
def run_scheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    sched = BlockingScheduler(timezone=WIB)

    @sched.scheduled_job('cron', hour=9, minute=0)
    def msg_open():
        if _is_trading_day():
            _notify_once_open()

    @sched.scheduled_job('cron', hour=15, minute=0)
    def msg_close():
        if _is_trading_day():
            _notify_once_close()

    @sched.scheduled_job('cron', minute="*/15")
    def scanner():
        if not (_is_trading_day() and _market_hours()):
            return

        conn = sqlite3.connect("alerts.db", check_same_thread=False)
        tickers = conn.execute("SELECT ticker FROM alerts").fetchall()

        for (ticker,) in tickers:
            if scan_one(ticker):
                BOT.send_message(
                    CHAT_ID,
                    f"🔊 15-min breakout detected!\nSymbol: <b>{ticker}</b>"
                )

        conn.close()

    sched.start()


# ----------------------------------------------------
# STUBS (FOR TELEGRAM /alert SYSTEM)
# ----------------------------------------------------
def create_alert(ticker: str, webhook_url: str) -> str:
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
