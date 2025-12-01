import os, re, sqlite3, telebot
from tradingview import create_alert, delete_alert

BOT = telebot.TeleBot(os.getenv("TOKEN"))
conn = sqlite3.connect("alerts.db", check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS alerts(ticker TEXT PRIMARY KEY, aid TEXT)")

@BOT.message_handler(commands=["add"])
def add(m):
    tkrs = re.findall(r"[A-Z0-9]+", m.text.upper())
    added, skipped = [], []
    for t in tkrs:
        if conn.execute("SELECT 1 FROM alerts WHERE ticker=?", (t,)).fetchone():
            skipped.append(t); continue
        aid = create_alert(t, os.getenv("WEBHOOK_ROOT")+"/webhook")
        conn.execute("INSERT INTO alerts(ticker,aid) VALUES (?,?)", (t, aid))
        added.append(t)
    conn.commit()
    BOT.reply_to(m, f"✅ {added}\n🟡 {skipped}")

@BOT.message_handler(commands=["remove","list","wipe"])
def manage(m):
    cmd = m.text.split()[0][1:]
    if cmd == "list":
        rows = [r[0] for r in conn.execute("SELECT ticker FROM alerts").fetchall()]
        BOT.reply_to(m, "📋 " + "\n".join(rows) if rows else "📋 kosong")
    elif cmd == "remove":
        t = m.text.split()[1].upper()
        row = conn.execute("SELECT aid FROM alerts WHERE ticker=?", (t,)).fetchone()
        if row:
            delete_alert(row[0])
            conn.execute("DELETE FROM alerts WHERE ticker=?", (t,))
            conn.commit()
        BOT.reply_to(m, f"🗑️ {t} dihapus")
    elif cmd == "wipe":
        for (aid,) in conn.execute("SELECT aid FROM alerts").fetchall():
            delete_alert(aid)
        conn.execute("DELETE FROM alerts")
        conn.commit()
        BOT.reply_to(m, "🗑️ semua dihapus")

def bot_poll():
    BOT.infinity_polling()
