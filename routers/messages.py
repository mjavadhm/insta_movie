import re
from aiogram import Router, F
from aiogram.types import Message
from models import get_session
from services.movie_service import search_movie_by_title, fetch_and_save_movie
from services.reel_service import get_post_caption, extract_movie_title_from_caption
from logger import get_logger

# Initialize router
router = Router(name="messages")
logger = get_logger()

# Updated Regex to detect any Instagram post link (p, reel, tv)
INSTAGRAM_POST_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

@router.message(F.text)
async def handle_text_message(message: Message):
    """
    Handles incoming text messages, routing them to the appropriate handler.
    """
    if not message.text:
        return

    text = message.text.strip()

    # Check if the message is an Instagram post link
    if re.match(INSTAGRAM_POST_REGEX, text):
        await handle_instagram_post_link(message)
    else:
        await handle_movie_title_query(message)


async def handle_instagram_post_link(message: Message):
    """
    Handle Instagram post links to extract movie titles and save them.
    """
    post_url = message.text.strip()
    await message.reply("در حال پردازش لینک اینستاگرام...")

    # 1. Get post caption
    caption = await get_post_caption(post_url)
    if not caption:
        await message.reply("خطا در دریافت کپشن. ممکن است پست خصوصی باشد یا لینک نامعتبر باشد.")
        return

    # 2. Extract movie title from caption using AI
    await message.reply("کپشن دریافت شد. در حال استخراج نام فیلم...")
    movie_title_query = await extract_movie_title_from_caption(caption)
    if not movie_title_query:
        await message.reply("متاسفانه نتوانستم نام فیلمی از کپشن استخراج کنم.")
        return
    
    await message.reply(f"نام فیلم استخراج شد: «{movie_title_query}». حالا آن را جستجو و ذخیره می‌کنم.")
    
    # Reuse the logic for searching and saving the movie
    await process_movie_query(message, movie_title_query)


async def handle_movie_title_query(message: Message):
    """
    Handle text messages to search and save movies by title.
    """
    movie_title_query = message.text.strip()
    await message.reply(f"🔍 در حال جستجو برای «{movie_title_query}»...")
    await process_movie_query(message, movie_title_query)


async def process_movie_query(message: Message, movie_title_query: str):
    """
    A generic function to search for and save a movie based on a title query.
    """
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
            # fetch_and_save_movie itself checks for duplicates
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