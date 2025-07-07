
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

# Initialize bot and dispatcher
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set")
api_server = TelegramAPIServer.from_base(base="http://172.245.152.11:8081")

session = AiohttpSession(api=api_server)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
dp = Dispatcher()
# Function to get bot instance
def get_bot() -> Bot:
    return bot

# Function to get dispatcher instance
def get_dispatcher() -> Dispatcher:
    return dp
