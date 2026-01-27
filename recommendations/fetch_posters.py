import requests
import time
from recommendations.models import Movie

API_KEY = "2597fbf6"

def fetch_posters(limit=1000):
    movies = list(
        Movie.objects.filter(poster_url__isnull=True)[:limit]
    )

    print(f"Đang lấy poster cho {len(movies)} phim...")

    for movie in movies:
        url = f"http://www.omdbapi.com/?i={movie.tconst}&apikey={API_KEY}"

        try:
            res = requests.get(url, timeout=10).json()
            poster = res.get("Poster")

            if poster and poster != "N/A":
                movie.poster_url = poster
                movie.save()
                print(f"✔ {movie.primaryTitle}")
            else:
                print(f"✘ Không có poster: {movie.primaryTitle}")

            time.sleep(0.2)

        except Exception as e:
            print(f"⚠ Lỗi {movie.tconst}: {e}")
