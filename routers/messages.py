import re
import uuid
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.movie_service import search_and_save_movies_from_titles
from services.reel_service import get_post_caption, extract_movie_titles_from_caption
from logger import get_logger
from .callbacks import callback_movie_cache # Import the cache

router = Router(name="messages")
logger = get_logger()

INSTAGRAM_POST_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

@router.message(F.text)
async def handle_text_message(message: Message):
    if not message.text:
        return
    text = message.text.strip()
    match = re.search(INSTAGRAM_POST_REGEX, text)
    if match:
        await handle_instagram_post_link(message, match)
    else:
        await message.reply(f"در حال جستجو برای «{text}»...")
        result = await search_and_save_movies_from_titles([text])
        
        if result["saved"]:
            await message.answer(f"✅ فیلم «{result['saved'][0]}» با موفقیت پیدا و ذخیره شد.")
        else:
            await message.answer(f"❌ فیلمی با عنوان «{text}» پیدا نشد.")

async def handle_instagram_post_link(message: Message, match: re.Match):
    """
    Creates a single message with action buttons using short, unique identifiers.
    """
    shortcode = match.group(1)
    
    await message.reply("در حال پردازش لینک...")
    caption = await get_post_caption(shortcode) # Pass shortcode directly
    if not caption:
        await message.reply("خطا در دریافت کپشن.")
        return

    movie_titles = await extract_movie_titles_from_caption(caption)
    if not movie_titles:
        await message.reply("نام فیلمی در کپشن پیدا نشد.")
        return

    found_movies_text = "\n".join(f"• {title}" for title in movie_titles)
    response_text = f"از کپشن این پست، فیلم‌های زیر پیدا شد:\n\n{found_movies_text}"
    
    # --- Create short and safe callback data ---
    
    # 1. For adding movies
    callback_id = str(uuid.uuid4())
    callback_movie_cache[callback_id] = movie_titles

    # 2. For downloading video (the shortcode is already short)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ اضافه کردن به دیتابیس",
                callback_data=f"add_to_db_{callback_id}" # UPDATED: Changed callback data
            )
        ],
        [
            InlineKeyboardButton(
                text="📥 دانلود ویدیو اینستاگرام",
                callback_data=f"download_video_{shortcode}" # Use the shortcode
            )
        ]
    ])
    
    await message.answer(response_text, reply_markup=keyboard)