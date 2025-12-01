import os, json, time, datetime, requests
from playwright.sync_api import sync_playwright

TV_USER  = os.getenv("TV_USER")
TV_PASS  = os.getenv("TV_PASS")
EXCHANGE = os.getenv("EXCHANGE") or "IDX"

# ---------- helpers ----------
WIB = datetime.timezone(datetime.timedelta(hours=7))

def _is_trading_day():
    """Mon-Fri and not Indonesian holiday (simple list)."""
    today = datetime.datetime.now(WIB).date()
    if today.weekday() >= 5:                      # Sat/Sun
        return False
    # minimal holiday list – add more if needed
    holidays = {2024: [12, 25], 2025: [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]}
    if today.month == 12 and today.day == 25: return False
    if today.month == 1  and today.day == 1:  return False
    return True

def _market_hours():
    """09:00-15:00 WIB"""
    now = datetime.datetime.now(WIB).time()
    open  = datetime.time(9, 0)
    close = datetime.time(15, 0)
    return open <= now <= close

def _send_bot_msg(text):
    """Quick Telegram helper without importing telebot here."""
    token   = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=5)

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

# ---------- volume-breakout WITH live check ----------
def create_alert(ticker: str, webhook_url: str) -> str:
    # 0. market open?
    if not (_is_trading_day() and _market_hours()):
        _send_bot_msg(f"📴 Market tutup – skip breakout check {ticker}")
        return "closed"

    browser, page = _new_page()
    try:
        # 1. open 15m chart
        page.goto(f"https://www.tradingview.com/symbols/{EXCHANGE}-{ticker}/?interval=15")
        page.wait_for_load_state("networkidle")

        # 2. grab LAST 15m candle volume via TV’s runtime
        vol = page.evaluate("""
            () => {
                const chart = tvWidget.activeChart;
                const series = chart.series;
                const data = series.bars().bars;
                if (data.length < 2) return null;
                const last = data[data.length-1];
                return last.volume;
            }
        """)
        if vol is None:
            _send_bot_msg(f"⚠️ Tidak dapat data live – skip breakout check {ticker}")
            browser.close()
            return "no_data"

        # 3. compare vs 10-period average (same indicator already on chart)
        avg = page.evaluate("""
            () => {
                const ind = tvWidget.activeChart.getStudyById(
                    tvWidget.activeChart.getAllStudies().find(s=>s.name.includes("Breakout Volume")).id
                );
                return ind.outputs.avg_vol;   // indicator exposes this
            }
        """)
        ratio = vol / avg if avg else 0

        # 4. only CREATE alert if live volume ≥ 1.5×
        if ratio < 1.5:
            browser.close()
            return "no_breakout"

        # 5. else create the alert exactly as before
        page.click('[data-name="alerts"]')
        page.click('text=Create alert')
        page.fill('[placeholder="Message"]', json.dumps(
            {"ticker":"{{ticker}}","close":{{close}},"volume":{{volume}},"time":"{{time}}"}
        ))
        page.fill('[placeholder="Webhook URL"]', webhook_url)
        page.click('button:has-text("Create")')
        time.sleep(2)
        alert_id = page.url.split("/")[-1]
    finally:
        browser.close()
    return alert_id

# ---------- delete ----------
def delete_alert(alert_id: str):
    browser, page = _new_page()
    page.goto(f"https://www.tradingview.com/uql/?alert_id={alert_id}")
    page.click('button[title="Delete"]')
    page.click('button:has-text("Delete")')
    browser.close()
