import os, dotenv, threading
# 1. load .env BEFORE any local import that needs TOKEN
dotenv.load_dotenv()

from fastapi import FastAPI
from telegrambot import bot_poll
from tradingview import run_scheduler

app = FastAPI()   # kept for future webhook use

if __name__ == "__main__":
    # 2. start services
    threading.Thread(target=bot_poll, daemon=True).start()
    run_scheduler()          # blocking – runs 15-min scanner
