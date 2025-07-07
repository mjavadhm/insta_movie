import re
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from models import get_session
from services.movie_service import search_movie_by_title, fetch_and_save_movie
from services.reel_service import get_post_caption, extract_movie_titles_from_caption
from logger import get_logger

router = Router(name="messages")
logger = get_logger()

INSTAGRAM_POST_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

@router.message(F.text)
async def handle_text_message(message: Message):
    if not message.text:
        return
    text = message.text.strip()
    if re.match(INSTAGRAM_POST_REGEX, text):
        await handle_instagram_post_link(message)
    else:
        await process_movie_query(message, [text]) # Treat as a list with one item

async def handle_instagram_post_link(message: Message):
    post_url = message.text.strip()
    await message.reply("در حال پردازش لینک...")
    caption = await get_post_caption(post_url)
    if not caption:
        await message.reply("خطا در دریافت کپشن.")
        return

    await message.reply("کپشن دریافت شد. در حال استخراج نام فیلم‌ها...")
    movie_titles = await extract_movie_titles_from_caption(caption)
    if not movie_titles:
        await message.reply("نام فیلمی در کپشن پیدا نشد.")
        return
    
    await message.reply(f"پیدا شد: {', '.join(movie_titles)}. در حال جستجو و ذخیره...")
    await process_movie_query(message, movie_titles)

async def process_movie_query(message: Message, movie_titles: list):
    """Searches for and saves a list of movies."""
    for title in movie_titles:
        try:
            search_result = await search_movie_by_title(title)
            if not search_result:
                await message.reply(f"❌ فیلمی با عنوان «{title}» پیدا نشد.")
                continue

            tmdb_id = search_result.get("id")
            found_title = search_result.get("title")
            
            async for session in get_session():
                saved_movie = await fetch_and_save_movie(session, tmdb_id)
                
                response_text = ""
                if saved_movie:
                    logger.info(f"فیلم '{saved_movie.title}' ذخیره شد.")
                    response_text = f"🎉 فیلم «{saved_movie.title}» با موفقیت ذخیره شد!"
                else:
                    logger.info(f"فیلم '{found_title}' از قبل موجود بود.")
                    response_text = f"✅ فیلم «{found_title}» از قبل در دیتابیس وجود داشت."

                # Add a button to add to watchlist
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="➕ افزودن به لیست تماشا", 
                        callback_data=f"watchlist_add_{tmdb_id}"
                    )]
                ])
                await message.reply(response_text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error processing query '{title}': {e}", exc_info=True)
            await message.reply(f"😥 مشکلی در پردازش «{title}» پیش آمد.")