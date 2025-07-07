from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update
from models import get_session
from models.movie import Movie
from logger import get_logger

router = Router(name="callbacks")
logger = get_logger()

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
        
        # Update the button to show it's added
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
        # Remove the message containing the removed movie
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}", exc_info=True)
        await callback.answer("❌ خطایی رخ داد.", show_alert=True)

@router.callback_query(F.data == "already_in_watchlist")
async def already_in_watchlist_callback(callback: CallbackQuery):
    """Handles clicks on buttons for movies already in the watchlist."""
    await callback.answer("این فیلم از قبل در لیست شما قرار دارد.", show_alert=False)