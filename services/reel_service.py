from instagrapi import Client
from instagrapi.exceptions import LoginRequired
import google.generativeai as genai
from config import GEMINI_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from logger import get_logger
from typing import List, Optional
import os
from pathlib import Path

logger = get_logger()
cl = Client()

SESSION_FILE = f"./instagrapi_session.json"

try:
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        logger.info("✅ instagrapi session loaded successfully from file.")
        cl.get_timeline_feed()
    else:
        logger.info("Session file not found, logging in with username and password.")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        logger.info("✅ Logged in and saved instagrapi session to file.")
except LoginRequired:
    logger.warning("Session has expired. Re-logging in...")
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    cl.dump_settings(SESSION_FILE)
    logger.info("✅ Re-logged in and saved new instagrapi session to file.")
except Exception as e:
    logger.error(f"❌ An unexpected error occurred during Instagram client setup: {e}")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

async def get_post_caption(shortcode: str) -> Optional[str]:
    """Downloads the caption of an Instagram Post using its shortcode."""
    try:
        media_pk = cl.media_pk_from_url(f"https://www.instagram.com/p/{shortcode}/")
        media_info = cl.media_info(media_pk)
        return media_info.caption_text
    except Exception as e:
        logger.error(f"Error fetching post caption for {shortcode}: {e}")
        return None

async def download_instagram_video(shortcode: str) -> Optional[str]:
    """Downloads an Instagram video using its shortcode and returns the file path."""
    try:
        logger.info(f"Downloading video for shortcode: {shortcode}")
        download_dir = Path("downloads")
        download_dir.mkdir(exist_ok=True)
        media_pk = cl.media_pk_from_url(f"https://www.instagram.com/p/{shortcode}/")
        video_path = cl.video_download(media_pk, folder=download_dir)
        logger.info(f"Video downloaded successfully: {video_path}")
        return str(video_path)
    except Exception as e:
        logger.error(f"Error downloading video from {shortcode}: {e}", exc_info=True)
        return None

async def extract_movie_titles_from_caption(caption: str) -> List[str]:
    """Uses a generative AI model to extract all movie titles from a caption."""
    if not caption:
        return []
    try:
        prompt = f"""
        From the following text, please extract all movie titles you can find.
        List each movie title on a new line. Do not provide any extra explanation, just the titles.

        Text: "{caption}"

        Movie Titles:
        """
        response = await model.generate_content_async(prompt)
        if response.parts:
            titles = [title.strip() for title in response.parts[0].text.split('\n') if title.strip()]
            return titles
        return []
    except Exception as e:
        logger.error(f"Error extracting movie titles with AI: {e}")
        return []