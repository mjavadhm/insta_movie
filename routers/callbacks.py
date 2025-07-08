from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select, update
from logger import get_logger
from services.reel_service import download_instagram_video
from services.movie_service import search_movie_by_title, fetch_and_save_movie # UPDATED: Imports
from models import get_session # UPDATED: Imports
from models.movie import Movie # UPDATED: Imports
import os
import uuid

router = Router(name="callbacks")
logger = get_logger()

# A temporary cache to store movie titles linked to a unique ID
# { "unique_id": ["Movie 1", "Movie 2"] }
callback_movie_cache = {}

# Helper function to format movie info text
def _format_movie_text_for_user(movie: Movie) -> str:
    text = f"🎬 <b>{movie.title}</b>\n\n"
    if movie.release_date:
        text += f"📅 <b>تاریخ انتشار:</b> {movie.release_date.strftime('%Y-%m-%d')}\n"
    if movie.vote_average:
        text += f"⭐ <b>امتیاز:</b> {movie.vote_average}/10\n"
    if movie.genres:
        text += f"🎭 <b>ژانرها:</b> {', '.join(movie.genres)}\n"
    if movie.overview:
        overview = movie.overview[:300] + "..." if len(movie.overview) > 300 else movie.overview
        text += f"\n📝 <b>خلاصه:</b>\n{overview}\n"
    return text


@router.callback_query(F.data.startswith("add_to_db_"))
async def add_to_database_callback(callback: CallbackQuery):
    """
    Retrieves movie titles from cache, saves them one by one,
    and sends a confirmation message with a watchlist button for each.
    """
    callback_id = callback.data.replace("add_to_db_", "")
    titles = callback_movie_cache.pop(callback_id, None)

    if not titles:
        await callback.message.edit_text("❌ این درخواست منقضی شده یا مشکلی پیش آمده است. لطفاً لینک را دوباره ارسال کنید.")
        await callback.answer()
        return

    await callback.message.edit_text(f"⏳ در حال پردازش {len(titles)} فیلم. این عملیات ممکن است کمی طول بکشد...")
    await callback.answer()

    async for session in get_session():
        for title in titles:
            status_message = ""
            movie_to_show = None
            
            try:
                search_result = await search_movie_by_title(title)
                if not search_result:
                    await callback.message.answer(f"❌ فیلمی با عنوان «{title}» پیدا نشد.")
                    continue

                tmdb_id = search_result.get("id")
                
                result = await session.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
                existing_movie = result.scalar_one_or_none()

                if existing_movie:
                    status_message = f"ℹ️ فیلم «{existing_movie.title}» از قبل در دیتابیس وجود داشت."
                    movie_to_show = existing_movie
                else:
                    new_movie = await fetch_and_save_movie(session, tmdb_id)
                    if new_movie:
                        status_message = f"✅ فیلم «{new_movie.title}» با موفقیت به دیتابیس اضافه شد."
                        movie_to_show = new_movie
                    else:
                        # Handle race condition or other errors
                        await callback.message.answer(f"❌ خطایی در ذخیره‌سازی فیلم «{title}» رخ داد.")
                        continue
                
                if movie_to_show:
                    info_caption = _format_movie_text_for_user(movie_to_show)
                    full_caption = f"{status_message}\n\n{info_caption}"
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="➕ افزودن به لیست تماشا",
                            callback_data=f"watchlist_add_{movie_to_show.tmdb_id}"
                        )]
                    ])

                    if movie_to_show.poster_url:
                        await callback.message.answer_photo(
                            photo=movie_to_show.poster_url,
                            caption=full_caption,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                    else:
                        await callback.message.answer(
                            text=full_caption,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )

            except Exception as e:
                logger.error(f"Error processing and sending movie '{title}': {e}", exc_info=True)
                await callback.message.answer(f"خطایی در پردازش فیلم '{title}' رخ داد.")

    await callback.message.delete()


@router.callback_query(F.data.startswith("download_video_"))
async def download_video_callback(callback: CallbackQuery):
    """Handles the download video button press using a shortcode."""
    shortcode = callback.data.replace("download_video_", "")
    await callback.message.edit_text("⏳ در حال دانلود ویدیو، لطفاً صبر کنید...")
    
    try:
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