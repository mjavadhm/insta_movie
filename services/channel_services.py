import asyncio
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from bot import get_bot
from logger import get_logger
from config import ERROR_CHANNEL_ID

logger = get_logger()

class ChannelService:
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.bot = get_bot()

    async def send_movie_post(self, movie):
        """Send a movie poster and info to the channel with a follow button."""
        try:
            movie_text = self._format_movie_text(movie)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔔 Follow Movie",
                    callback_data=f"follow_movie_{movie.tmdb_id}"
                )]
            ])

            if movie.poster_url:
                try:
                    message = await self.bot.send_photo(
                        chat_id=self.channel_id,
                        photo=movie.poster_url,
                        caption=movie_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    logger.info(f"Sent movie post with poster: {movie.title}")
                    return message
                except TelegramBadRequest as e:
                    logger.warning(f"Failed to send photo for {movie.title}: {e}. Falling back to text.")
                    pass

            message = await self.bot.send_message(
                chat_id=self.channel_id,
                text=movie_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"Sent movie post as text: {movie.title}")
            return message

        except Exception as e:
            logger.error(f"Error sending movie post {movie.title}: {e}", exc_info=True)
            return None

    def _format_movie_text(self, movie):
        """Format movie information for a Telegram post."""
        text = f"🎬 <b>{movie.title}</b>\n\n"

        if movie.release_date:
            text += f"📅 <b>Release Date:</b> {movie.release_date.strftime('%B %d, %Y')}\n"

        if movie.vote_average:
            rating_emoji = "⭐" * max(1, min(5, round(movie.vote_average / 2)))
            text += f"⭐ <b>Rating:</b> {movie.vote_average}/10 {rating_emoji}\n"

        if movie.genres:
            genres_text = ", ".join(movie.genres)
            text += f"🎭 <b>Genres:</b> {genres_text}\n"

        if movie.overview:
            overview = movie.overview
            if len(overview) > 300:
                overview = overview[:297] + "..."
            text += f"\n📝 <b>Overview:</b>\n{overview}\n"

        if movie.popularity:
            text += f"\n🔥 <b>Popularity:</b> {movie.popularity:.1f}\n"

        text += f"\n🎥 <i>Follow this movie to get updates!</i>"

        return text

    async def send_bulk_movies(self, movies, delay_between_posts=2):
        """Send multiple movies to the channel with a delay between posts."""
        sent_count = 0
        failed_count = 0

        for movie in movies:
            try:
                message = await self.send_movie_post(movie)
                if message:
                    sent_count += 1
                else:
                    failed_count += 1

                if delay_between_posts > 0:
                    await asyncio.sleep(delay_between_posts)

            except Exception as e:
                logger.error(f"Error sending movie {movie.title}: {e}")
                failed_count += 1

        logger.info(f"Bulk send completed: {sent_count} sent, {failed_count} failed")
        return sent_count, failed_count

    async def send_status_message(self, text):
        """Send a status message to the channel."""
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                parse_mode="HTML"
            )
            logger.info("Sent status message to channel")
        except Exception as e:
            logger.error(f"Error sending status message: {e}", exc_info=True)