# routers/messages.py

import re
import uuid
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.movie_service import search_and_save_movies_from_titles
from services.reel_service import get_post_caption, extract_movie_titles_from_caption
from logger import get_logger
from .callbacks import callback_movie_cache

router = Router(name="messages")
logger = get_logger()

INSTAGRAM_POST_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

@router.message(F.text)
async def handle_text_message(message: Message):
    # ... (بدون تغییر)
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
    # ... (تغییر در این بخش)
    shortcode = match.group(1)
    
    await message.reply("در حال پردازش لینک...")
    caption = await get_post_caption(shortcode)
    if not caption:
        await message.reply("خطا در دریافت کپشن.")
        return

    movie_titles = await extract_movie_titles_from_caption(caption)
    if not movie_titles:
        response_text = "نام فیلمی در کپشن پیدا نشد."
        

    else:
        found_movies_text = "\n".join(f"• {title}" for title in movie_titles)
        response_text = f"از کپشن این پست، فیلم‌های زیر پیدا شد:\n\n{found_movies_text}"
    
    callback_id = str(uuid.uuid4())
    callback_movie_cache[callback_id] = movie_titles

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ اضافه کردن به دیتابیس",
                callback_data=f"add_to_db_{callback_id}"
            )
        ],
        # دکمه جدید برای تحلیل صدا
        [
            InlineKeyboardButton(
                text="🔎 تحلیل از روی صدا",
                callback_data=f"audio_analyze_{shortcode}" # <-- دکمه جدید
            )
        ],
        [
            InlineKeyboardButton(
                text="📥 دانلود ویدیو اینستاگرام",
                callback_data=f"download_video_{shortcode}"
            )
        ]
    ])
    
    await message.answer(response_text, reply_markup=keyboard)