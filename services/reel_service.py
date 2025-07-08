from instagrapi import Client
from instagrapi.exceptions import LoginRequired
import google.generativeai as genai
from config import GEMINI_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
from logger import get_logger
from typing import List, Optional
import os
from pathlib import Path
from moviepy.video.io.VideoFileClip import VideoFileClip
import asyncio

logger = get_logger()
cl = Client()

SESSION_FILE = f"./instagrapi_session.json"

try:
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        logger.info("✅ Instagrapi session loaded successfully from file.")
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
    """Fetches the caption of an Instagram post."""
    try:
        media_pk = cl.media_pk_from_url(f"https://www.instagram.com/p/{shortcode}/")
        media_info = cl.media_info(media_pk)
        return media_info.caption_text
    except Exception as e:
        logger.error(f"Error fetching post caption for {shortcode}: {e}")
        return None

async def download_instagram_video(shortcode: str) -> Optional[str]:
    """Downloads a video from an Instagram post."""
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
    """Extracts movie titles from a given text using a generative AI model."""
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
async def extract_movie_titles_from_video(shortcode: str) -> list[str]:
    """
    Downloads a video, uploads it to Gemini, waits for it to be active,
    and then uses it to find movie titles.
    """
    video_path = None
    video_file = None
    try:
        video_path = await download_instagram_video(shortcode)
        if not video_path:
            return []

        logger.info(f"Uploading video file {video_path} to Gemini...")
        loop = asyncio.get_event_loop()
        video_file_response = await loop.run_in_executor(
            None, lambda: genai.upload_file(path=video_path)
        )
        logger.info(f"File upload started for {video_file_response.name}. Waiting for it to become active.")

        while video_file_response.state.name == "PROCESSING":
            await asyncio.sleep(5)
            video_file_response = await loop.run_in_executor(
                None, lambda: genai.get_file(name=video_file_response.name)
            )
            logger.info(f"Current file state: {video_file_response.state.name}")

        if video_file_response.state.name != "ACTIVE":
            logger.error(f"File {video_file_response.name} failed processing. State: {video_file_response.state.name}")
            return []

        logger.info(f"File {video_file_response.name} is now ACTIVE.")
        video_file = video_file_response

        prompt = """
        From the video, please extract all movie titles you can find.
        If theres None please try to found the movie or movies that are in the video.
        List each movie title on a new line. Do not provide any extra explanation, just the titles.
        If no movie title is mentioned, return an empty response.
        """

        response = await model.generate_content_async([prompt, video_file])

        if response.parts:
            titles = [title.strip() for title in response.parts[0].text.split('\n') if title.strip()]
            logger.info(f"Found titles from video: {titles}")
            return titles
        return []

    except Exception as e:
        logger.error(f"Error extracting titles from video for {shortcode}: {e}", exc_info=True)
        return []
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
            logger.info("Cleaned up temporary video file.")
        
        if video_file:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: genai.delete_file(name=video_file.name))
                logger.info(f"Deleted remote file {video_file.name}.")
            except Exception as e:
                logger.error(f"Failed to delete remote file {video_file.name}: {e}")