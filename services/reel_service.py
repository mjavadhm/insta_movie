import instaloader
import re
import google.generativeai as genai
from config import GEMINI_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from logger import get_logger
from typing import List

logger = get_logger()

# --- بخش جدید برای لاگین در اینستاگرام ---

# یک نمونه سراسری از Instaloader برای استفاده مجدد از جلسه ایجاد می‌کنیم
L = instaloader.Instaloader(
    error_messages=True,
    save_metadata=False,
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    compress_json=False,
)

# اگر اطلاعات کاربری موجود بود، تلاش برای لاگین
if INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD:
    logger.info(f"در حال تلاش برای ورود به اینستاگرام با نام کاربری: {INSTAGRAM_USERNAME}")
    try:
        # تلاش برای بارگذاری جلسه از فایل برای جلوگیری از لاگین مکرر
        L.load_session_from_file(INSTAGRAM_USERNAME)
        logger.info("جلسه اینستاگرام با موفقیت از فایل بارگذاری شد.")
    except FileNotFoundError:
        # اگر فایل جلسه وجود نداشت، لاگین کرده و جلسه را ذخیره می‌کنیم
        try:
            L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            L.save_session_to_file(INSTAGRAM_USERNAME)
            logger.info("لاگین موفقیت‌آمیز بود و جلسه اینستاگرام ذخیره شد.")
        except Exception as e:
            logger.error(f"خطا در هنگام لاگین به اینستاگرام: {e}")
    except Exception as e:
        logger.error(f"خطا در بارگذاری جلسه اینستاگرام: {e}")
else:
    logger.warning("اطلاعات کاربری اینستاگرام ارائه نشده است. ربات در حالت ناشناس اجرا می‌شود که ممکن است ناپایدار باشد.")

# --- پایان بخش جدید ---

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
        # از نمونه لاگین‌شده و سراسری Instaloader استفاده می‌کنیم
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
            # Split the text by newlines and clean up each title
            titles = [title.strip() for title in response.parts[0].text.split('\n') if title.strip()]
            return titles
        return []

    except Exception as e:
        logger.error(f"Error extracting movie titles with AI: {e}")
        return []