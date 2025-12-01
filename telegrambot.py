import os, re, sqlite3, telebot
from tradingview import create_alert, delete_alert   # currently stubs

TOKEN   = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BOT = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ------------------------------
# Database
# ------------------------------
conn = sqlite3.connect("alerts.db", check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS alerts(
    ticker TEXT PRIMARY KEY,
    aid    TEXT
)
""")

# ------------------------------
# Commands
# ------------------------------
@BOT.message_handler(commands=["start", "help"])
def help_(m):
    BOT.reply_to(m,
        "📊 <b>IDX Breakout Volume (15m)</b>\n\n"
        "Commands:\n"
        "<code>/add BBCA</code> → mulai pantau\n"
        "<code>/remove BBCA</code> → berhenti\n"
        "<code>/list</code> → daftar aktif\n"
        "<code>/wipe</code> → hapus semua"
    )

@BOT.message_handler(commands=["add"])
def add(m):
    # Extract tickers (A–Z + 0–9)
    tickers = re.findall(r"[A-Z0-9]+", m.text.upper())

    if not tickers:
        return BOT.reply_to(m, "❌ Format salah. Contoh: <code>/add BBCA</code>")

    added, skipped = [], []

    for t in tickers:
        exists = conn.execute(
            "SELECT 1 FROM alerts WHERE ticker=?",
            (t,)
        ).fetchone()

        if exists:
            skipped.append(t)
            continue

        # TradingView alert creation
        aid = create_alert(t, "")  # webhook unused for now

        conn.execute(
            "INSERT OR IGNORE INTO alerts(ticker,aid) VALUES (?,?)",
            (t, aid)
        )
        added.append(t)

    conn.commit()

    BOT.reply_to(
        m,
        f"✅ Ditambah: <b>{', '.join(added) or '-'}</b>\n"
        f"🟡 Lewat (sudah ada): <b>{', '.join(skipped) or '-'}</b>"
    )

@BOT.message_handler(commands=["remove"])
def rem(m):
    parts = m.text.split()

    if len(parts) != 2:
        return BOT.reply_to(m, "❌ Format: <code>/remove TICKER</code>")

    ticker = parts[1].upper()

    row = conn.execute(
        "SELECT aid FROM alerts WHERE ticker=?",
        (ticker,)
    ).fetchone()

    if not row:
        return BOT.reply_to(m, f"❌ {ticker} tidak ditemukan")

    delete_alert(row[0])
    conn.execute("DELETE FROM alerts WHERE ticker=?", (ticker,))
    conn.commit()

    BOT.reply_to(m, f"🗑️ <b>{ticker}</b> dihapus")

@BOT.message_handler(commands=["list"])
def lst(m):
    rows = conn.execute("SELECT ticker FROM alerts").fetchall()

    if not rows:
        return BOT.reply_to(m, "📋 kosong")

    tickers = "\n".join(f"• {r[0]}" for r in rows)

    BOT.reply_to(
        m,
        "<b>📋 Daftar Ticker Aktif:</b>\n" + tickers
    )

@BOT.message_handler(commands=["wipe"])
def wipe(m):
    all_alerts = conn.execute(
        "SELECT aid FROM alerts"
    ).fetchall()

    for (aid,) in all_alerts:
        delete_alert(aid)

    conn.execute("DELETE FROM alerts")
    conn.commit()

    BOT.reply_to(m, "🗑️
