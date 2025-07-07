from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from models import get_session
from models.movie import Movie
from services.movie_service import fetch_and_save_upcoming_movies, get_random_movie
from services.channel_services import ChannelService
from config import MOVIES_CHANNEL_ID
from logger import get_logger

# Initialize router
router = Router(name="commands")
logger = get_logger()

def _format_movie_text_for_user(movie: Movie) -> str:
    """اطلاعات فیلم را برای پیام کاربر فرمت‌بندی می‌کند."""
    # Title with emoji
    text = f"🎬 <b>{movie.title}</b>\n\n"
    
    # Release date
    if movie.release_date:
        text += f"📅 <b>تاریخ انتشار:</b> {movie.release_date.strftime('%d %B %Y')}\n"
    
    # Rating
    if movie.vote_average:
        rating_emoji = "⭐" * max(1, min(5, round(movie.vote_average / 2)))
        text += f"⭐ <b>امتیاز:</b> {movie.vote_average}/10 {rating_emoji}\n"
    
    # Genres
    if movie.genres:
        genres_text = ", ".join(movie.genres)
        text += f"🎭 <b>ژانرها:</b> {genres_text}\n"
    
    # Overview
    if movie.overview:
        # Limit overview length for Telegram
        overview = movie.overview
        if len(overview) > 300:
            overview = overview[:297] + "..."
        text += f"\n📝 <b>خلاصه داستان:</b>\n{overview}\n"
    
    return text

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    try:
        await message.answer(
            "👋 خوش آمدید! من ربات فیلم شما هستم.\n"
            "برای دیدن دستورات موجود از /help استفاده کنید."
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    try:
        help_text = (
            "دستورات موجود:\n"
            "/start - شروع کار با ربات\n"
            "/help - نمایش این پیام راهنما\n"
            "/random - نمایش یک فیلم تصادفی از دیتابیس\n"
            "/post_upcoming - ارسال فیلم‌های آینده به کانال (فقط ادمین)\n"
            "/check_updates - بررسی آپدیت فیلم‌ها (فقط ادمین)"
        )
        await message.answer(help_text)
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)

@router.message(Command("random"))
async def cmd_random(message: Message):
    """دستور /random برای نمایش یک فیلم تصادفی"""
    try:
        async for session in get_session():
            random_movie = await get_random_movie(session)

            if not random_movie:
                await message.answer("هنوز هیچ فیلمی در دیتابیس وجود ندارد.")
                return

            caption = _format_movie_text_for_user(random_movie)

            if random_movie.poster_url:
                await message.answer_photo(
                    photo=random_movie.poster_url,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    text=caption,
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Error in random command: {e}", exc_info=True)
        await message.answer("❌ خطایی در هنگام نمایش فیلم تصادفی رخ داد.")

@router.message(Command("post_upcoming"))
async def cmd_post_upcoming(message: Message):
    """Handle /post_upcoming command - fetch and post upcoming movies"""
    try:
        # Check if user is authorized (you might want to add admin check here)
        user_id = message.from_user.id if message.from_user else None
        
        await message.answer("🔄 در حال دریافت فیلم‌های آینده...")
        
        # Fetch upcoming movies
        async for session in get_session():
            movies = await fetch_and_save_upcoming_movies(session, page=1, limit=10)
            
            if not movies:
                await message.answer("❌ فیلم جدیدی برای نمایش یافت نشد.")
                return
            
            # Send status message
            await message.answer(
                f"✅ {len(movies)} فیلم جدید یافت شد!\n"
                f"🔄 در حال ارسال به کانال..."
            )
            
            # Post to channel
            channel_service = ChannelService(MOVIES_CHANNEL_ID)
            sent_count, failed_count = await channel_service.send_bulk_movies(movies)
            
            # Send summary
            summary = (
                f"📊 <b>خلاصه ارسال:</b>\n"
                f"✅ با موفقیت ارسال شد: {sent_count}\n"
                f"❌ ارسال ناموفق: {failed_count}\n"
                f"📺 کانال: کانال فیلم‌ها"
            )
            await message.answer(summary, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Error in post upcoming command: {e}", exc_info=True)
        await message.answer("❌ خطایی در هنگام ارسال فیلم‌ها رخ داد.")

@router.message(Command("check_updates"))
async def cmd_check_updates(message: Message):
    """Handle /check_updates command - force check for movie updates"""
    try:
        from services.movie_scheduler import MovieUpdateScheduler
        
        await message.answer("🔄 در حال بررسی آپدیت فیلم‌ها...")
        
        # Create scheduler and force check
        scheduler = MovieUpdateScheduler(MOVIES_CHANNEL_ID)
        await scheduler.force_check_now()
        
        await message.answer("✅ بررسی آپدیت فیلم‌ها با موفقیت انجام شد!")
        
    except Exception as e:
        logger.error(f"Error in check updates command: {e}", exc_info=True)
        await message.answer("❌ خطایی در هنگام بررسی آپدیت‌ها رخ داد.")