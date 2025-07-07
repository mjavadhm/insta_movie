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

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("👋 خوش آمدید! برای راهنمایی /help را بزنید.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "دستورات موجود:\n"
        "/start - شروع کار\n"
        "/help - نمایش راهنما\n"
        "/random - پیشنهاد یک فیلم تصادفی\n"
        "/watchlist - نمایش لیست تماشای شما\n\n"
        "همچنین می‌توانید نام فیلم یا لینک پستی از اینستاگرام را برای من ارسال کنید!"
    )
    await message.answer(help_text)

@router.message(Command("random"))
async def cmd_random(message: Message):
    async for session in get_session():
        movie = await get_random_movie(session)
        if not movie:
            await message.answer("هنوز فیلمی در دیتابیس نیست.")
            return

        caption = _format_movie_text_for_user(movie)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="➕ افزودن به لیست تماشا", 
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
    await message.answer("⏳ در حال دریافت لیست تماشای شما...")
    async for session in get_session():
        result = await session.execute(
            select(Movie).where(Movie.is_tracked == True).order_by(Movie.created_at.desc())
        )
        watchlist_movies = result.scalars().all()

    if not watchlist_movies:
        await message.answer("لیست تماشای شما خالی است. می‌توانید با جستجوی فیلم یا ارسال لینک اینستاگرام، فیلم‌ها را به آن اضافه کنید.")
        return

    await message.answer(f"شما {len(watchlist_movies)} فیلم در لیست تماشای خود دارید:")
    for movie in watchlist_movies:
        caption = _format_movie_text_for_user(movie)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑️ حذف از لیست تماشا",
                callback_data=f"watchlist_remove_{movie.tmdb_id}"
            )]
        ])
        if movie.poster_url:
            await message.answer_photo(photo=movie.poster_url, caption=caption, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text=caption, reply_markup=keyboard, parse_mode="HTML")