import asyncio
import os
from pathlib import Path
from typing import List, Optional, Dict
import aiohttp
import google.generativeai as genai
from config import GEMINI_API_KEY, FASTSAVER_API_TOKEN
from logger import get_logger

logger = get_logger()

# Configure Generative AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-pro')

# API endpoint
API_BASE_URL = "https://fastsaverapi.com/get-info"

async def _fetch_media_info(shortcode: str) -> Optional[Dict]:
    """Fetches media information from the FastSaverAPI."""
    params = {
        "url": f"https://www.instagram.com/p/{shortcode}/",
        "token": FASTSAVER_API_TOKEN
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_BASE_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if not data.get("error"):
                        logger.info(f"✅ Successfully fetched info for {shortcode}")
                        return data
                    else:
                        logger.error(f"❌ API returned an error for {shortcode}: {data.get('message')}")
                        return None
                else:
                    logger.error(f"❌ Failed to fetch info for {shortcode}. Status: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception while fetching media info for {shortcode}: {e}", exc_info=True)
        return None

async def get_post_caption(shortcode: str) -> Optional[str]:
    """Fetches the caption of an Instagram post using the new API."""
    media_info = await _fetch_media_info(shortcode)
    return media_info.get("caption") if media_info else None

async def download_instagram_video(shortcode: str) -> Optional[str]:
    """Downloads a video from an Instagram post using the new API."""
    media_info = await _fetch_media_info(shortcode)
    if not media_info or not media_info.get("download_url"):
        logger.error(f"Could not get download URL for {shortcode}")
        return None

    download_url = media_info["download_url"]
    
    try:
        logger.info(f"Downloading video for shortcode: {shortcode}")
        download_dir = Path("downloads")
        download_dir.mkdir(exist_ok=True)
        # Use the shortcode to create a unique filename
        video_path = download_dir / f"{shortcode}.mp4"

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    with open(video_path, "wb") as f:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            f.write(chunk)
                    logger.info(f"✅ Video downloaded successfully: {video_path}")
                    return str(video_path)
                else:
                    logger.error(f"❌ Failed to download video from {download_url}. Status: {response.status}")
                    return None

    except Exception as e:
        logger.error(f"❌ Error downloading video from {shortcode}: {e}", exc_info=True)
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
        logger.error(f"❌ Error extracting movie titles with AI: {e}")
        return []

async def extract_movie_titles_from_video(shortcode: str) -> list[str]:
    """
    Downloads a video, uploads it to Gemini, and uses it to find movie titles.
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

        logger.info(f"✅ File {video_file_response.name} is now ACTIVE.")
        video_file = video_file_response

        prompt = """
        From the video, please extract all movie titles you can find.
        If there are none, please try to find the movie or movies that are in the video.
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
        logger.error(f"❌ Error extracting titles from video for {shortcode}: {e}", exc_info=True)
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
                logger.error(f"❌ Failed to delete remote file {video_file.name}: {e}")