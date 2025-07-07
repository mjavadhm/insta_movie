import instaloader
import re
import google.generativeai as genai
from config import GEMINI_API_KEY
from logger import get_logger

logger = get_logger()

# Configure the generative AI model
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Regex to extract shortcode from any Instagram URL
SHORTCODE_REGEX = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"

async def get_post_caption(post_url: str) -> str | None:
    """
    Downloads the caption of an Instagram Post (Reel, Photo, Video) using its URL.
    """
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

async def extract_movie_title_from_caption(caption: str) -> str | None:
    """
    Uses a generative AI model to extract the movie title from a caption.
    """
    if not caption:
        return None
    
    try:
        prompt = f"""
        From the following text, please extract only the movie title. 
        Do not provide any extra explanation, just the title.

        Text: "{caption}"

        Movie Title:
        """
        response = await model.generate_content_async(prompt)
        # Access the text of the first part of the response
        if response.parts:
            return response.parts[0].text.strip()
        return None

    except Exception as e:
        logger.error(f"Error extracting movie title with AI: {e}")
        return None