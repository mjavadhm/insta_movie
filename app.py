import asyncio
import logging
from aiogram.types import BotCommand
from bot import dp, bot
from routers import commands_router, callbacks_router, messages_router

# Get logger
logger = get_logger()

# Register routers
dp.include_router(commands_router)
dp.include_router(callbacks_router)
dp.include_router(messages_router)

async def set_commands():
    """Set bot commands in menu"""
    commands = [
        BotCommand(command="start", description="شروع کار با ربات"),
        BotCommand(command="help", description="نمایش راهنما"),
        BotCommand(command="random", description="پیشنهاد یک فیلم تصادفی"),
        BotCommand(command="watchlist", description="نمایش لیست تماشای من"),
    ]
    await bot.set_my_commands(commands)

async def main():
    """Main function"""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting bot...")

    try:
        await set_commands()
        logger.info("Bot is running...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())