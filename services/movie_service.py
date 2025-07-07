from datetime import datetime
import tmdbsimple as tmdb
from sqlalchemy import select
from sqlalchemy.sql.expression import func  # این خط را اضافه کنید
from sqlalchemy.exc import IntegrityError

from models.movie import Movie
from models.person import Person
from models.movie_cast import MovieCast
from models.movie_crew import MovieCrew
from config import TMDB_API_KEY

# تنظیم کلید API
tmdb.API_KEY = TMDB_API_KEY


async def fetch_and_save_upcoming_movies(session, page=1, limit=None):
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
            print(f"❌ خطا در ذخیره فیلم {item['id']}: {e}")
    return saved_movies


async def search_movie_by_title(query: str) -> dict | None:
    """
    یک فیلم را بر اساس عنوان در TMDb جستجو می‌کند و اولین نتیجه را برمی‌گرداند.
    """
    try:
        search = tmdb.Search()
        response = search.movie(query=query)
        if response['results']:
            return response['results'][0]  # بازگرداندن اولین و محتمل‌ترین نتیجه
        return None
    except Exception as e:
        print(f"❌ خطا در جستجوی فیلم '{query}': {e}")
        return None


async def fetch_and_save_movie(session, tmdb_id: int):
    """
    1. اطلاعات فیلم و credits را از TMDb می‌گیرد
    2. با save_movie_with_cast_and_crew در دیتابیس ذخیره می‌کند
    """
    # بررسی اینکه آیا فیلم از قبل در دیتابیس وجود دارد یا نه
    result = await session.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if result.scalar_one_or_none():
        print(f"ℹ️ فیلم با TMDB ID {tmdb_id} از قبل در دیتابیس وجود دارد.")
        return None # اگر وجود داشت، نیازی به ذخیره مجدد نیست

    # 1. فراخوانی اطلاعات پایه فیلم
    movie_api = tmdb.Movies(tmdb_id)
    info = movie_api.info()
    release_date_str = info.get("release_date")
    release_date = None
    if release_date_str:
        try:
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass # اگر فرمت تاریخ اشتباه بود، نادیده بگیر

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

    # 2. فراخوانی credits برای cast و crew
    credits = movie_api.credits()
    cast_list = credits.get("cast", [])
    crew_list = credits.get("crew", [])

    # 3. ذخیره در دیتابیس
    movie = await save_movie_with_cast_and_crew(session, movie_data, cast_list, crew_list)
    return movie


async def get_or_create_person(session, person_data):
    """
    بر اساس tmdb_id یک Person را یا پیدا می‌کند یا می‌سازد.
    """
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
    """
    ذخیره فیلم به همراه بازیگران و عوامل در دیتابیس
    """
    # ساخت شیء Movie
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
    await session.flush()  # تا movie.id تولید بشه

    # اضافه کردن بازیگران
    for c in cast_list:
        person = await get_or_create_person(session, c)
        cast_entry = MovieCast(
            movie_id=movie.id,
            person_id=person.id,
            character_name=c.get("character"),
            cast_order=c.get("order"),
        )
        session.add(cast_entry)

    # اضافه کردن عوامل
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
        # ممکن است فیلمی دیگر همزمان ذخیره شده باشد
        result = await session.execute(
            select(Movie).where(Movie.tmdb_id == movie_data["tmdb_id"])
        )
        return result.scalar_one_or_none()


async def get_random_movie(session):
    """
    یک فیلم تصادفی از دیتابیس برمی‌گرداند.
    """
    result = await session.execute(
        select(Movie).order_by(func.random()).limit(1)
    )
    return result.scalar_one_or_none()