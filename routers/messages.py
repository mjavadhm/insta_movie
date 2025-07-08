import re
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.movie_service import search_and_save_movies_from_titles
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
    match = re.search(INSTAGRAM_POST_REGEX, text)
    if match:
        await handle_instagram_post_link(message, match)
    else:
        # اگر لینک نبود، مثل قبل فقط همان یک فیلم را پردازش می‌کند
        await message.reply(f"در حال جستجو برای «{text}»...")
        result = await search_and_save_movies_from_titles([text])
        
        if result["saved"]:
            await message.answer(f"✅ فیلم «{result['saved'][0]}» با موفقیت پیدا و ذخیره شد.")
        else:
            await message.answer(f"❌ فیلمی با عنوان «{text}» پیدا نشد.")

async def handle_instagram_post_link(message: Message, match: re.Match):
    """
    یک پیام واحد با دکمه‌های عملیاتی برای لینک اینستاگرام ارسال می‌کند
    """
    post_url = message.text.strip()
    shortcode = match.group(1)
    
    await message.reply("در حال پردازش لینک...")
    caption = await get_post_caption(post_url)
    if not caption:
        await message.reply("خطا در دریافت کپشن.")
        return

    movie_titles = await extract_movie_titles_from_caption(caption)
    if not movie_titles:
        await message.reply("نام فیلمی در کپشن پیدا نشد.")
        return

    # ساخت پیام اصلی
    found_movies_text = "\n".join(f"• {title}" for title in movie_titles)
    response_text = f"از کپشن این پست، فیلم‌های زیر پیدا شد:\n\n{found_movies_text}"
    
    # ساخت دکمه‌ها
    # برای دکمه "افزودن همه"، عناوین را با یک جداکننده خاص به هم می‌چسبانیم
    titles_payload = "|||".join(movie_titles)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ افزودن همه به لیست تماشا",
                callback_data=f"add_all_{titles_payload}"
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