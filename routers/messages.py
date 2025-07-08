import re
import uuid
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.movie_service import search_and_save_movies_from_titles
from services.reel_service import get_post_caption, extract_movie_titles_from_caption
from logger import get_logger
from .callbacks import callback_movie_cache

router = Router(name="messages")
logger = get_logger()

INSTAGRAM_POST_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

@router.message(F.text)
async def handle_text_message(message: Message):
    """Handles incoming text messages, either a movie title or an Instagram link."""
    if not message.text:
        return
    text = message.text.strip()
    match = re.search(INSTAGRAM_POST_REGEX, text)
    if match:
        await handle_instagram_post_link(message, match)
    else:
        await message.reply(f"Searching for '{text}'...")
        result = await search_and_save_movies_from_titles([text])

        if result["saved"]:
            await message.answer(f"✅ The movie '{result['saved'][0]}' was successfully found and saved.")
        else:
            await message.answer(f"❌ No movie with the title '{text}' was found.")


async def handle_instagram_post_link(message: Message, match: re.Match):
    """Handles Instagram post links to extract movie titles."""
    shortcode = match.group(1)

    await message.reply("Processing the link...")
    caption = await get_post_caption(shortcode)
    if not caption:
        await message.reply("Error getting the caption.")
        return

    movie_titles = await extract_movie_titles_from_caption(caption)
    if not movie_titles:
        response_text = "No movie titles were found in the caption."
    else:
        found_movies_text = "\n".join(f"• {title}" for title in movie_titles)
        response_text = f"The following movies were found in the post's caption:\n\n{found_movies_text}"

    callback_id = str(uuid.uuid4())
    callback_movie_cache[callback_id] = movie_titles

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add to Database",
                callback_data=f"add_to_db_{callback_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔎 Analyze video",
                callback_data=f"video_analyze_{shortcode}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📥 Download Instagram Video",
                callback_data=f"download_video_{shortcode}"
            )
        ]
    ])

    await message.answer(response_text, reply_markup=keyboard)