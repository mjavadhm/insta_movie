from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select, update
from logger import get_logger
from services.reel_service import download_instagram_video, extract_movie_titles_from_audio
from services.movie_service import search_movie_by_title, fetch_and_save_movie
from models import get_session
from models.movie import Movie
import os
import uuid

router = Router(name="callbacks")
logger = get_logger()

# A temporary cache to store movie titles linked to a unique ID
callback_movie_cache = {}

def _format_movie_text_for_user(movie: Movie) -> str:
    """Helper function to format movie info text for the user"""
    text = f"🎬 <b>{movie.title}</b>\n\n"
    if movie.release_date:
        text += f"📅 <b>Release Date:</b> {movie.release_date.strftime('%Y-%m-%d')}\n"
    if movie.vote_average:
        text += f"⭐ <b>Rating:</b> {movie.vote_average}/10\n"
    if movie.genres:
        text += f"🎭 <b>Genres:</b> {', '.join(movie.genres)}\n"
    if movie.overview:
        overview = movie.overview[:300] + "..." if len(movie.overview) > 300 else movie.overview
        text += f"\n📝 <b>Overview:</b>\n{overview}\n"
    return text


@router.callback_query(F.data.startswith("add_to_db_"))
async def add_to_database_callback(callback: CallbackQuery):
    """
    Retrieves movie titles from the cache, saves them one by one,
    and sends a confirmation message with a watchlist button for each.
    """
    callback_id = callback.data.replace("add_to_db_", "")
    titles = callback_movie_cache.pop(callback_id, None)

    if not titles:
        await callback.message.edit_text("❌ This request has expired or an error occurred. Please send the link again.")
        await callback.answer()
        return

    await callback.answer(f"⏳ Processing {len(titles)} movie(s)...")

    async for session in get_session():
        for title in titles:
            status_message = ""
            movie_to_show = None

            try:
                search_result = await search_movie_by_title(title)
                if not search_result:
                    await callback.message.answer(f"❌ Movie with title '{title}' not found.")
                    continue

                tmdb_id = search_result.get("id")

                result = await session.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
                existing_movie = result.scalar_one_or_none()

                if existing_movie:
                    status_message = f"ℹ️ The movie '{existing_movie.title}' already exists in the database."
                    movie_to_show = existing_movie
                else:
                    new_movie = await fetch_and_save_movie(session, tmdb_id)
                    if new_movie:
                        status_message = f"✅ The movie '{new_movie.title}' was successfully added to the database."
                        movie_to_show = new_movie
                    else:
                        await callback.message.answer(f"❌ An error occurred while saving the movie '{title}'.")
                        continue

                if movie_to_show:
                    info_caption = _format_movie_text_for_user(movie_to_show)
                    full_caption = f"{status_message}\n\n{info_caption}"

                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="➕ Add to Watchlist",
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
                await callback.message.answer(f"An error occurred while processing the movie '{title}'.")


@router.callback_query(F.data.startswith("video_analyze_"))
async def analyze_audio_callback(callback: CallbackQuery):
    """Handles the audio analysis button press."""
    shortcode = callback.data.replace("audio_analyze_", "")
    sent_m = await callback.message.answer("⏳ Analyzing video audio... This may take a few minutes. Please be patient.")
    await callback.answer()

    try:
        titles = await extract_movie_titles_from_audio(shortcode)

        if titles:
            found_movies_text = "\n".join(f"• {title}" for title in titles)
            response_text = f"The following movies were identified from the video:\n\n{found_movies_text}"

            callback_id = str(uuid.uuid4())
            callback_movie_cache[callback_id] = titles

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Add to Database",
                        callback_data=f"add_to_db_{callback_id}"
                    )
                ]
            ])
            await sent_m.edit_text(response_text, reply_markup=keyboard)
        else:
            await sent_m.edit_text("❌ Unfortunately, no movie was found in the video's audio, or an error occurred during analysis.")

    except Exception as e:
        logger.error(f"Error in audio analysis callback for {shortcode}: {e}", exc_info=True)
        await sent_m.edit_text("❌ An unexpected error occurred during the audio analysis process.")


@router.callback_query(F.data.startswith("download_video_"))
async def download_video_callback(callback: CallbackQuery):
    """Handles the download video button press using a shortcode."""
    shortcode = callback.data.replace("download_video_", "")
    sent_m = await callback.message.answer("⏳ Downloading video, please wait...")

    try:
        video_path = await download_instagram_video(shortcode)

        if video_path and os.path.exists(video_path):
            if os.path.getsize(video_path) > 50 * 1024 * 1024:
                await sent_m.edit_text("❌ Video size is larger than 50 MB.")
                return

            video_file = FSInputFile(video_path)
            await callback.message.answer_video(video=video_file, caption=f"Video from: `{shortcode}`")
            await callback.message.delete()
        else:
            await sent_m.edit_text("❌ Unfortunately, the video download failed.")

    except Exception as e:
        logger.error(f"Error sending video {shortcode}: {e}", exc_info=True)
        await sent_m.edit_text("❌ An error occurred while sending the video.")
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

        await callback.answer("✅ Added to watchlist!", show_alert=True)

        if callback.message and callback.message.reply_markup:
            updated_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ In Watchlist",
                    callback_data="already_in_watchlist"
                )]
            ])
            await callback.message.edit_reply_markup(reply_markup=updated_keyboard)

    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}", exc_info=True)
        await callback.answer("❌ An error occurred.", show_alert=True)


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

        await callback.answer("🗑️ Removed from watchlist.", show_alert=True)
        await callback.message.delete()

    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}", exc_info=True)
        await callback.answer("❌ An error occurred.", show_alert=True)


@router.callback_query(F.data == "already_in_watchlist")
async def already_in_watchlist_callback(callback: CallbackQuery):
    """Handles clicks on buttons for movies already in the watchlist."""
    await callback.answer("This movie is already in your list.", show_alert=False)