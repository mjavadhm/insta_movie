import instaloader
import re
import google.generativeai as genai
from config import GEMINI_API_KEY
from logger import get_logger
from typing import List

logger = get_logger()

# Configure the generative AI model
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Regex to extract shortcode from any Instagram URL
SHORTCODE_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

async def get_post_caption(post_url: str) -> str | None:
    """Downloads the caption of an Instagram Post."""
    try:
        match = re.search(SHORTCODE_REGEX, post_url)
        if not match:
            logger.error(f"Could not find shortcode in URL: {post_url}")
            return None
        
        shortcode = match.group(1)
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return post.caption
    except Exception as e:
        logger.error(f"Error fetching post caption for {post_url}: {e}")
        return None

async def extract_movie_titles_from_caption(caption: str) -> List[str]:
    """
    Uses a generative AI model to extract all movie titles from a caption.
    Returns a list of titles.
    """
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
            # Split the text by newlines and clean up each title
            titles = [title.strip() for title in response.parts[0].text.split('\n') if title.strip()]
            return titles
        return []

    except Exception as e:
        logger.error(f"Error extracting movie titles with AI: {e}")
        return []