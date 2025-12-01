import os, threading
from fastapi import FastAPI
from telegrambot import bot_poll
from tradingview import run_scheduler   # free scanner

app = FastAPI()   # kept for future use

if __name__ == "__main__":
    # 1. telegram bot (non-blocking)
    threading.Thread(target=bot_poll, daemon=True).start()
    # 2. 15-min scanner (blocking, runs forever)
    run_scheduler()
