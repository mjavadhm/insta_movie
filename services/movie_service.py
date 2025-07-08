from datetime import datetime
from typing import Dict, List
import tmdbsimple as tmdb
from sqlalchemy import select
from sqlalchemy.sql.expression import func
from sqlalchemy.exc import IntegrityError
from models import get_session
from models.movie import Movie
from models.person import Person
from models.movie_cast import MovieCast
from models.movie_crew import MovieCrew
from config import TMDB_API_KEY
from logger import get_logger

tmdb.API_KEY = TMDB_API_KEY


async def fetch_and_save_upcoming_movies(session, page=1, limit=None):
    """Fetches upcoming movies from TMDb and saves them to the database."""
    movies_api = tmdb.Movies()
    response = movies_api.upcoming(page=page)

    results = response.get("results", [])
    if limit:
        results = results[:limit]

    saved_movies = []
    for item in results:
        try:
            movie = await fetch_and_save_movie(session, tmdb_id=item["id"])
            if movie:
                saved_movies.append(movie)
        except Exception as e:
            print(f"❌ Error saving movie {item['id']}: {e}")
    return saved_movies


async def search_movie_by_title(query: str) -> dict | None:
    """Searches for a movie by title on TMDb and returns the first result."""
    try:
        search = tmdb.Search()
        response = search.movie(query=query)
        if response['results']:
            return response['results'][0]
        return None
    except Exception as e:
        print(f"❌ Error searching for movie '{query}': {e}")
        return None


async def fetch_and_save_movie(session, tmdb_id: int):
    """
    Fetches movie details and credits from TMDb and saves them to the database.
    """
    result = await session.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if result.scalar_one_or_none():
        print(f"ℹ️ Movie with TMDB ID {tmdb_id} already exists in the database.")
        return None

    movie_api = tmdb.Movies(tmdb_id)
    info = movie_api.info()
    release_date_str = info.get("release_date")
    release_date = None
    if release_date_str:
        try:
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    movie_data = {
        "tmdb_id": tmdb_id,
        "title": info.get("title"),
        "overview": info.get("overview"),
        "release_date": release_date,
        "popularity": info.get("popularity"),
        "vote_average": info.get("vote_average"),
        "genres": [g["name"] for g in info.get("genres", [])],
        "poster_url": None if not info.get("poster_path") else
                      f"https://image.tmdb.org/t/p/original{info['poster_path']}"
    }

    credits = movie_api.credits()
    cast_list = credits.get("cast", [])
    crew_list = credits.get("crew", [])

    movie = await save_movie_with_cast_and_crew(session, movie_data, cast_list, crew_list)
    return movie


async def get_or_create_person(session, person_data):
    """Finds a person by tmdb_id or creates a new one."""
    result = await session.execute(
        select(Person).where(Person.tmdb_id == person_data["id"])
    )
    person = result.scalar_one_or_none()
    if person:
        return person

    person = Person(
        tmdb_id=person_data["id"],
        name=person_data["name"],
        profile_url=person_data.get("profile_path"),
        known_for_department=person_data.get("known_for_department"),
    )
    session.add(person)
    await session.flush()
    return person


async def save_movie_with_cast_and_crew(session, movie_data, cast_list, crew_list):
    """Saves a movie along with its cast and crew to the database."""
    movie = Movie(
        tmdb_id=movie_data["tmdb_id"],
        title=movie_data["title"],
        overview=movie_data.get("overview"),
        release_date=movie_data.get("release_date"),
        popularity=movie_data.get("popularity"),
        vote_average=movie_data.get("vote_average"),
        genres=movie_data.get("genres", []),
        poster_url=movie_data.get("poster_url"),
    )
    session.add(movie)
    await session.flush()

    for c in cast_list:
        person = await get_or_create_person(session, c)
        cast_entry = MovieCast(
            movie_id=movie.id,
            person_id=person.id,
            character_name=c.get("character"),
            cast_order=c.get("order"),
        )
        session.add(cast_entry)

    for c in crew_list:
        person = await get_or_create_person(session, c)
        crew_entry = MovieCrew(
            movie_id=movie.id,
            person_id=person.id,
            job=c.get("job"),
            department=c.get("department"),
        )
        session.add(crew_entry)

    try:
        await session.commit()
        return movie
    except IntegrityError:
        await session.rollback()
        result = await session.execute(
            select(Movie).where(Movie.tmdb_id == movie_data["tmdb_id"])
        )
        return result.scalar_one_or_none()


async def get_random_movie(session):
    """Returns a random movie from the database."""
    result = await session.execute(
        select(Movie).order_by(func.random()).limit(1)
    )
    return result.scalar_one_or_none()


async def search_and_save_movies_from_titles(titles: List[str]) -> Dict[str, List[str]]:
    """
    Searches for a list of movie titles, saves them, and returns a summary of the operation.
    """
    saved_movies = []
    failed_titles = []

    async for session in get_session():
        for title in titles:
            try:
                search_result = await search_movie_by_title(title)
                if not search_result:
                    failed_titles.append(title)
                    continue

                tmdb_id = search_result.get("id")
                movie = await fetch_and_save_movie(session, tmdb_id)
                if movie:
                    saved_movies.append(movie.title)
                else:
                    result = await session.execute(select(Movie.title).where(Movie.tmdb_id == tmdb_id))
                    existing_title = result.scalar_one_or_none()
                    if existing_title:
                        saved_movies.append(existing_title)

            except Exception as e:
                get_logger().error(f"Error processing title '{title}': {e}")
                failed_titles.append(title)

    return {"saved": saved_movies, "failed": failed_titles}