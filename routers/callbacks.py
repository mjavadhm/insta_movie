from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select, update
from logger import get_logger
from services.reel_service import download_instagram_video
from services.movie_service import search_and_save_movies_from_titles
import os
import uuid

router = Router(name="callbacks")
logger = get_logger()

# A temporary cache to store movie titles linked to a unique ID
# { "unique_id": ["Movie 1", "Movie 2"] }
callback_movie_cache = {}

@router.callback_query(F.data.startswith("add_all_"))
async def add_all_to_watchlist_callback(callback: CallbackQuery):
    """
    Retrieves a list of movie titles from the cache using a unique ID and saves them.
    """
    callback_id = callback.data.replace("add_all_", "")
    titles = callback_movie_cache.pop(callback_id, None)

    if not titles:
        await callback.message.edit_text("❌ این درخواست منقضی شده یا مشکلی پیش آمده است. لطفاً لینک را دوباره ارسال کنید.")
        await callback.answer()
        return
        
    await callback.message.edit_text("⏳ در حال پردازش و افزودن فیلم‌ها به لیست تماشا...")
    
    result = await search_and_save_movies_from_titles(titles)
    
    saved_count = len(result["saved"])
    failed_count = len(result["failed"])
    
    summary_text = f"عملیات انجام شد:\n\n"
    if saved_count > 0:
        summary_text += f"✅ {saved_count} فیلم با موفقیت به لیست تماشا اضافه شد.\n"
    if failed_count > 0:
        failed_list = "\n".join(f"- {title}" for title in result["failed"])
        summary_text += f"❌ {failed_count} فیلم پیدا نشد:\n{failed_list}"
        
    await callback.message.edit_text(summary_text, reply_markup=None)
    await callback.answer()

@router.callback_query(F.data.startswith("download_video_"))
async def download_video_callback(callback: CallbackQuery):
    """Handles the download video button press using a shortcode."""
    shortcode = callback.data.replace("download_video_", "")
    await callback.message.edit_text("⏳ در حال دانلود ویدیو، لطفاً صبر کنید...")
    
    try:
        # The service function now correctly accepts a shortcode
        video_path = await download_instagram_video(shortcode)
        
        if video_path and os.path.exists(video_path):
            if os.path.getsize(video_path) > 50 * 1024 * 1024:
                await callback.message.edit_text("❌ حجم ویدیو بیشتر از 50 مگابایت است.")
                return

            video_file = FSInputFile(video_path)
            await callback.message.answer_video(video=video_file, caption=f"Video from: `{shortcode}`")
            await callback.message.delete()
        else:
            await callback.message.edit_text("❌ متاسفانه دانلود ویدیو با مشکل مواجه شد.")
            
    except Exception as e:
        logger.error(f"Error sending video {shortcode}: {e}", exc_info=True)
        await callback.message.edit_text("❌ خطایی در ارسال ویدیو رخ داد.")
    finally:
        if 'video_path' in locals() and video_path and os.path.exists(video_path):
            os.remove(video_path)

# --- The rest of the file remains the same ---

@router.callback_query(F.data.startswith("watchlist_add_"))
async def add_to_watchlist_callback(callback: CallbackQuery):
    """Adds a movie to the user's watchlist."""
    try:
        tmdb_id = int(callback.data.replace("watchlist_add_", ""))
        async for session in get_session():
            await session.execute(
                update(Movie).where(Movie.tmdb_id == tmdb_id).values(is_tracked=True)
            )
            await session.commit()

        await callback.answer("✅ به لیست تماشا اضافه شد!", show_alert=True)
        
        if callback.message and callback.message.reply_markup:
            updated_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ در لیست تماشا", 
                    callback_data="already_in_watchlist"
                )]
            ])
            await callback.message.edit_reply_markup(reply_markup=updated_keyboard)

    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}", exc_info=True)
        await callback.answer("❌ خطایی رخ داد.", show_alert=True)

@router.callback_query(F.data.startswith("watchlist_remove_"))
async def remove_from_watchlist_callback(callback: CallbackQuery):
    """Removes a movie from the user's watchlist."""
    try:
        tmdb_id = int(callback.data.replace("watchlist_remove_", ""))
        async for session in get_session():
            await session.execute(
                update(Movie).where(Movie.tmdb_id == tmdb_id).values(is_tracked=False)
            )
            await session.commit()
            
        await callback.answer("🗑️ از لیست تماشا حذف شد.", show_alert=True)
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}", exc_info=True)
        await callback.answer("❌ خطایی رخ داد.", show_alert=True)

@router.callback_query(F.data == "already_in_watchlist")
async def already_in_watchlist_callback(callback: CallbackQuery):
    """Handles clicks on buttons for movies already in the watchlist."""
    await callback.answer("این فیلم از قبل در لیست شما قرار دارد.", show_alert=False)