import instaloader
import re
import google.generativeai as genai
from config import GEMINI_API_KEY, INSTAGRAM_USERNAME
from logger import get_logger
from typing import List
import os

logger = get_logger()
L = instaloader.Instaloader()

# --- MODIFIED LOGIN LOGIC ---
SESSION_FILE = f"./{INSTAGRAM_USERNAME}"

if INSTAGRAM_USERNAME and os.path.exists(SESSION_FILE):
    logger.info(f"Attempting to load session from file: {SESSION_FILE}")
    try:
        L.load_session_from_file(INSTAGRAM_USERNAME, SESSION_FILE)
        logger.info("✅ Instagram session loaded successfully from file.")
    except Exception as e:
        logger.error(f"❌ Could not load session from file: {e}. Please regenerate the session file.")
else:
    logger.warning("⚠️ Instagram username not set or session file not found.")
    logger.warning("The bot will run unauthenticated and may be unstable.")

# --- END OF MODIFIED LOGIC ---

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

SHORTCODE_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

async def get_post_caption(post_url: str) -> str | None:
    """Downloads the caption of an Instagram Post."""
    try:
        match = re.search(SHORTCODE_REGEX, post_url)
        if not match:
            logger.error(f"Could not find shortcode in URL: {post_url}")
            return None
        
        shortcode = match.group(1)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return post.caption
    except Exception as e:
        logger.error(f"Error fetching post caption for {post_url}: {e}")
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