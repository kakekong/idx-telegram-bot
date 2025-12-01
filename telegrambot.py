import os, re, sqlite3, telebot
from tradingview import create_alert, delete_alert  # now stubs

TOKEN   = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BOT     = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("alerts.db", check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS alerts(ticker TEXT PRIMARY KEY, aid TEXT)")

@BOT.message_handler(commands=["start","help"])
def help_(m):
    BOT.reply_to(m, "Bot breakout volume IDX 15-menit (FREE)\n"
                    "/add TICKER → mulai pantau\n"
                    "/remove TICKER → berhenti\n"
                    "/list → lihat aktif\n"
                    "/wipe → hentikan semua")

@BOT.message_handler(commands=["add"])
def add(m):
    tickers = re.findall(r"[A-Z0-9]+", m.text.upper())
    added, skipped = [], []
    for t in tickers:
        if conn.execute("SELECT 1 FROM alerts WHERE ticker=?", (t,)).fetchone():
            skipped.append(t); continue
        aid = create_alert(t, "")          # webhook_url not used
        conn.execute("INSERT OR IGNORE INTO alerts(ticker,aid) VALUES (?,?)", (t, aid))
        added.append(t)
    conn.commit()
    BOT.reply_to(m, f"✅ {added}\n🟡 {skipped}")

@BOT.message_handler(commands=["remove"])
def rem(m):
    t = m.text.split()[1].upper() if len(m.text.split())==2 else None
    if not t: BOT.reply_to(m, "❌ /remove TICKER"); return
    row = conn.execute("SELECT aid FROM alerts WHERE ticker=?", (t,)).fetchone()
    if row:
        delete_alert(row[0])
        conn.execute("DELETE FROM alerts WHERE ticker=?", (t,))
        conn.commit()
    BOT.reply_to(m, f"🗑️ {t} dihapus")

@BOT.message_handler(commands=["list"])
def lst(m):
    rows = [r[0] for r in conn.execute("SELECT ticker FROM alerts").fetchall()]
    BOT.reply_to(m, "📋 " + "\n".join(rows) if rows else "kosong")

@BOT.message_handler(commands=["wipe"])
def wipe(m):
    for (aid,) in conn.execute("SELECT aid FROM alerts").fetchall():
        delete_alert(aid)
    conn.execute("DELETE FROM alerts")
    conn.commit()
    BOT.reply_to(m, "🗑️ semua dihapus")

def bot_poll():
    BOT.infinity_polling()
