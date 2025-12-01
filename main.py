import threading, os
from fastapi import FastAPI, Request
from telegrambot import bot_poll
from tradingview import create_alert, delete_alert

app = FastAPI()

@app.post("/webhook")
async def webhook(r: Request):
    data = await r.json()
    msg = f"🔊 Breakout volume 15-menit!\nSimbol: {data['ticker']}\nHarga: {data['close']}\nVolume: {data['volume']}\nWaktu: {data['time']}"
    os.getenv("BOT").send_message(os.getenv("CHAT_ID"), msg)
    return "ok"

if __name__ == "__main__":
    threading.Thread(target=lambda: bot_poll(), daemon=True).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
