from instagrapi import Client
from instagrapi.exceptions import LoginRequired
import google.generativeai as genai
from config import GEMINI_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from logger import get_logger
from typing import List, Optional
import os
from pathlib import Path

logger = get_logger()

# --- New instagrapi Client Setup ---
cl = Client()

SESSION_FILE = f"./instagrapi_session.json"

try:
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        logger.info("✅ instagrapi session loaded successfully from file.")
        # Optional: Check if the session is still valid
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

# --- End of New Setup ---

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

async def get_post_caption(post_url: str) -> Optional[str]:
    """Downloads the caption of an Instagram Post using instagrapi."""
    try:
        media_pk = cl.media_pk_from_url(post_url)
        media_info = cl.media_info(media_pk)
        return media_info.caption_text
    except Exception as e:
        logger.error(f"Error fetching post caption for {post_url}: {e}")
        return None

async def download_instagram_video(post_url: str) -> Optional[str]:
    """Downloads an Instagram video using instagrapi and returns the file path."""
    try:
        logger.info(f"Downloading video for URL: {post_url}")
        
        # Create a temporary directory for downloads
        download_dir = Path("downloads")
        download_dir.mkdir(exist_ok=True)

        media_pk = cl.media_pk_from_url(post_url)
        video_path = cl.video_download(media_pk, folder=download_dir)
        
        logger.info(f"Video downloaded successfully: {video_path}")
        return str(video_path)
    except Exception as e:
        logger.error(f"Error downloading video from {post_url}: {e}", exc_info=True)
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