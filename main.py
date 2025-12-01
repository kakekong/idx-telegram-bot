import os
from dotenv import load_dotenv
from telebot import TeleBot

# Load environment variables
load_dotenv()

# Initialize the Telegram bot
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = TeleBot(TOKEN)

# Define command handlers
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Welcome to my bot! Type /help for help.")

@bot.message_handler(commands=['add'])
def add_stock(message):
    bot.reply_to(message, "Stock added!")

@bot.message_handler(commands=['remove'])
def remove_stock(message):
    bot.reply_to(message, "Stock removed!")

@bot.message_handler(commands=['list'])
def list_stocks(message):
    bot.reply_to(message, "Current stocks")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.reply_to(message, "Help message")

# Start polling for incoming messages
bot.polling()
