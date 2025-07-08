from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from models import get_session
from models.movie import Movie
from services.movie_service import get_random_movie
from logger import get_logger

router = Router(name="commands")
logger = get_logger()

def _format_movie_text_for_user(movie: Movie) -> str:
    """Formats movie information for display to the user."""
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

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handles the /start command."""
    await message.answer("👋 Welcome! Type /help for guidance.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handles the /help command."""
    help_text = (
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/random - Get a random movie suggestion\n"
        "/watchlist - View your watchlist\n\n"
        "You can also send me a movie title or a link to an Instagram post!"
    )
    await message.answer(help_text)

@router.message(Command("random"))
async def cmd_random(message: Message):
    """Handles the /random command by suggesting a random movie."""
    async for session in get_session():
        movie = await get_random_movie(session)
        if not movie:
            await message.answer("There are no movies in the database yet.")
            return

        caption = _format_movie_text_for_user(movie)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="➕ Add to Watchlist",
                callback_data=f"watchlist_add_{movie.tmdb_id}"
            )]
        ])

        if movie.poster_url:
            await message.answer_photo(photo=movie.poster_url, caption=caption, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text=caption, reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("watchlist"))
async def cmd_watchlist(message: Message):
    """Displays the user's watchlist."""
    await message.answer("⏳ Fetching your watchlist...")
    async for session in get_session():
        result = await session.execute(
            select(Movie).where(Movie.is_tracked == True).order_by(Movie.created_at.desc())
        )
        watchlist_movies = result.scalars().all()

    if not watchlist_movies:
        await message.answer("Your watchlist is empty. You can add movies by searching for them or sending an Instagram link.")
        return

    await message.answer(f"You have {len(watchlist_movies)} movie(s) in your watchlist:")
    for movie in watchlist_movies:
        caption = _format_movie_text_for_user(movie)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑️ Remove from Watchlist",
                callback_data=f"watchlist_remove_{movie.tmdb_id}"
            )]
        ])
        if movie.poster_url:
            await message.answer_photo(photo=movie.poster_url, caption=caption, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text=caption, reply_markup=keyboard, parse_mode="HTML")