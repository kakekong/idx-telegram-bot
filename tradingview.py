import os, json, time
from playwright.sync_api import sync_playwright

TV_USER  = os.getenv("TV_USER")
TV_PASS  = os.getenv("TV_PASS")
EXCHANGE = os.getenv("EXCHANGE") or "IDX"

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

def create_alert(ticker: str, webhook: str) -> str:
    browser, page = _new_page()
    page.goto(f"https://www.tradingview.com/symbols/{EXCHANGE}-{ticker}/?interval=15")
    page.wait_for_load_state("networkidle")
    # add indicator
    page.click('[data-name="indicators"]')
    page.fill('[placeholder="Search"]', "Breakout Volume Alert")
    page.click('text=Breakout Volume Alert')
    page.keyboard.press("Escape")
    # create alert
    page.click('[data-name="alerts"]')
    page.click('text=Create alert')
    page.fill('[placeholder="Message"]', json.dumps(
        {"ticker":"{{ticker}}","close":{{close}},"volume":{{volume}},"time":"{{time}}"}
    ))
    page.fill('[placeholder="Webhook URL"]', webhook)
    page.click('button:has-text("Create")')
    time.sleep(2)
    alert_id = page.url.split("/")[-1]
    browser.close()
    return alert_id

def delete_alert(alert_id: str):
    browser, page = _new_page()
    page.goto(f"https://www.tradingview.com/uql/?alert_id={alert_id}")
    page.click('button[title="Delete"]')
    page.click('button:has-text("Delete")')
    browser.close()
