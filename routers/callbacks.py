from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select, update
from models import get_session, Movie
from logger import get_logger
from services.reel_service import download_instagram_video
from services.movie_service import search_and_save_movies_from_titles # ایمپورت جدید
import os

router = Router(name="callbacks")
logger = get_logger()

@router.callback_query(F.data.startswith("add_all_"))
async def add_all_to_watchlist_callback(callback: CallbackQuery):
    """
    لیستی از فیلم‌ها را از callback_data گرفته و به دیتابیس اضافه می‌کند
    """
    await callback.message.edit_text("⏳ در حال پردازش و افزودن فیلم‌ها به لیست تماشا...")
    
    # استخراج عناوین از payload
    titles_payload = callback.data.replace("add_all_", "")
    titles = titles_payload.split("|||")
    
    result = await search_and_save_movies_from_titles(titles)
    
    saved_count = len(result["saved"])
    failed_count = len(result["failed"])
    
    # ساخت پیام نتیجه
    summary_text = f"عملیات انجام شد:\n\n"
    if saved_count > 0:
        summary_text += f"✅ {saved_count} فیلم با موفقیت به لیست تماشا اضافه شد.\n"
    if failed_count > 0:
        failed_list = "\n".join(f"- {title}" for title in result["failed"])
        summary_text += f"❌ {failed_count} فیلم پیدا نشد:\n{failed_list}"
        
    await callback.message.edit_text(summary_text, reply_markup=None) # حذف دکمه‌ها
    await callback.answer()

@router.callback_query(F.data.startswith("download_video_"))
async def download_video_callback(callback: CallbackQuery):
    """Handles the download video button press."""
    # The callback_data will now contain the FULL URL
    post_url = callback.data.replace("download_video_", "")
    
    await callback.message.edit_text("⏳ در حال دانلود ویدیو، لطفاً صبر کنید...")
    
    try:
        # Pass the full URL to the download function
        video_path = await download_instagram_video(post_url)
        
        if video_path and os.path.exists(video_path):
            if os.path.getsize(video_path) > 50 * 1024 * 1024:
                await callback.message.edit_text("❌ حجم ویدیو بیشتر از 50 مگابایت است.")
                return

            video_file = FSInputFile(video_path)
            await callback.message.answer_video(video=video_file)
            await callback.message.delete()
        else:
            await callback.message.edit_text("❌ متاسفانه دانلود ویدیو با مشکل مواجه شد.")
            
    except Exception as e:
        logger.error(f"Error sending video: {e}", exc_info=True)
        await callback.message.edit_text("❌ خطایی در ارسال ویدیو رخ داد.")
    finally:
        if 'video_path' in locals() and video_path and os.path.exists(video_path):
            os.remove(video_path)