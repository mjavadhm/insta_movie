from aiogram import Router, F
from aiogram.types import Message
from models import get_session
from services.movie_service import search_movie_by_title, fetch_and_save_movie
from logger import get_logger

# Initialize router
router = Router(name="messages")
logger = get_logger()

@router.message(F.text)
async def handle_text_for_movie(message: Message):
    """
    Handle text messages to search and save movies.
    """
    if not message.text:
        return

    movie_title_query = message.text.strip()
    await message.reply(f"🔍 در حال جستجو برای «{movie_title_query}»...")

    try:
        # Search for the movie by title
        search_result = await search_movie_by_title(movie_title_query)

        if not search_result:
            await message.reply(f"❌ فیلمی با عنوان «{movie_title_query}» پیدا نشد.")
            return

        tmdb_id = search_result.get("id")
        found_title = search_result.get("title")
        
        await message.reply(f"✅ فیلم «{found_title}» پیدا شد. در حال دریافت اطلاعات و ذخیره‌سازی...")

        # Get database session and save the movie
        async for session in get_session():
            # fetch_and_save_movie خودش چک می‌کند که فیلم تکراری نباشد
            saved_movie = await fetch_and_save_movie(session, tmdb_id)
            
            if saved_movie:
                logger.info(f"فیلم '{saved_movie.title}' با موفقیت در دیتابیس ذخیره شد.")
                await message.reply(
                    f"🎉 فیلم «{saved_movie.title}» با موفقیت در دیتابیس ذخیره شد!"
                )
            else:
                logger.info(f"فیلم '{found_title}' از قبل در دیتابیس موجود بود.")
                await message.reply(
                    f"✅ فیلم «{found_title}» از قبل در دیتابیس وجود داشت."
                )

    except Exception as e:
        logger.error(f"Error in movie processing handler: {e}", exc_info=True)
        await message.reply("😥 مشکلی در فرآیند پردازش و ذخیره فیلم پیش آمد.")