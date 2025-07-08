import asyncio
import logging
from aiogram.types import BotCommand
from bot import dp, bot
from routers import commands_router, callbacks_router, messages_router
from logger import get_logger

# Get logger
logger = get_logger()

# Register routers
dp.include_router(commands_router)
dp.include_router(callbacks_router)
dp.include_router(messages_router)

async def set_commands():
    """Set bot commands in the menu"""
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Show help"),
        BotCommand(command="random", description="Suggest a random movie"),
        BotCommand(command="watchlist", description="Show my watchlist"),
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