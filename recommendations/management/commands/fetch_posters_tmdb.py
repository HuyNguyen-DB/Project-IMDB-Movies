import time
import requests

from pymongo import MongoClient
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Lấy poster phim từ TMDb theo 2 bước: "
        "1) TMDb Find bằng IMDb ID, "
        "2) TMDb Search bằng tên phim + năm."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Số phim cần kiểm tra trong một lần chạy.",
        )

        parser.add_argument(
            "--sleep",
            type=float,
            default=0.25,
            help="Thời gian nghỉ giữa mỗi phim.",
        )

        parser.add_argument(
            "--retry-checked",
            action="store_true",
            help="Kiểm tra lại cả những phim đã từng kiểm tra poster.",
        )

        parser.add_argument(
            "--collection",
            type=str,
            default="recommendations_movie",
            help="Tên collection MongoDB chứa dữ liệu phim.",
        )

    def handle(self, *args, **options):
        tmdb_api_key = getattr(settings, "TMDB_API_KEY", "")

        if not tmdb_api_key:
            self.stderr.write(
                self.style.ERROR("Thiếu TMDB_API_KEY trong settings.py.")
            )
            return

        limit = options["limit"]
        sleep_time = options["sleep"]
        retry_checked = options["retry_checked"]
        collection_name = options["collection"]

        collection = self.get_movie_collection(collection_name)

        movies = self.get_movies_from_mongo(
            collection=collection,
            limit=limit,
            retry_checked=retry_checked,
        )

        total = len(movies)

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS("Không còn phim nào cần cập nhật poster bằng TMDb.")
            )
            return

        self.stdout.write(
            self.style.WARNING(f"Bắt đầu kiểm tra poster TMDb cho {total} phim...")
        )

        updated_count = 0
        tmdb_find_count = 0
        tmdb_search_count = 0
        no_poster_count = 0
        error_count = 0

        for index, movie in enumerate(movies, start=1):
            tconst = movie.get("tconst") or movie.get("_id")
            title = movie.get("primaryTitle") or "Không rõ tên"
            start_year = movie.get("startYear")

            if not tconst:
                no_poster_count += 1
                continue

            self.stdout.write(
                f"[{index}/{total}] Đang xử lý TMDb: {tconst} - {title}"
            )

            try:
                poster_url, poster_source = self.get_poster_by_tmdb_pipeline(
                    imdb_id=tconst,
                    title=title,
                    start_year=start_year,
                    tmdb_api_key=tmdb_api_key,
                )

                if poster_url:
                    update_data = {
                        "poster_url": poster_url,
                        "poster_checked": True,
                        "poster_updated_at": timezone.now(),
                        "poster_source": poster_source,
                    }

                    self.update_movie(collection, movie, update_data)

                    updated_count += 1

                    if poster_source == "tmdb_find":
                        tmdb_find_count += 1
                    elif poster_source == "tmdb_search":
                        tmdb_search_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  OK: Đã cập nhật poster từ {poster_source}"
                        )
                    )

                else:
                    update_data = {
                        "poster_checked": True,
                        "poster_updated_at": timezone.now(),
                        "poster_source": "tmdb_not_found",
                    }

                    self.update_movie(collection, movie, update_data)

                    no_poster_count += 1

                    self.stdout.write(
                        self.style.WARNING(
                            f"  TMDb không tìm thấy poster: {title}"
                        )
                    )

            except requests.RequestException as exc:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(f"  Lỗi request TMDb {tconst}: {exc}")
                )

            except Exception as exc:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(f"  Lỗi không xác định {tconst}: {exc}")
                )

            time.sleep(sleep_time)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Hoàn tất cập nhật poster bằng TMDb."))
        self.stdout.write(f"Đã cập nhật poster: {updated_count}")
        self.stdout.write(f"  - TMDb Find IMDb ID: {tmdb_find_count}")
        self.stdout.write(f"  - TMDb Search title + year: {tmdb_search_count}")
        self.stdout.write(f"TMDb không tìm thấy poster: {no_poster_count}")
        self.stdout.write(f"Lỗi: {error_count}")

    def get_movie_collection(self, collection_name):
        db_config = settings.DATABASES.get("default", {})
        db_name = db_config.get("NAME")

        if not db_name:
            raise Exception("Không tìm thấy NAME trong DATABASES['default'].")

        client_config = db_config.get("CLIENT", {})
        host = (
            client_config.get("host")
            or client_config.get("HOST")
            or "mongodb://localhost:27017/"
        )
        port = client_config.get("port") or client_config.get("PORT")

        if isinstance(host, str) and host.startswith("mongodb"):
            client = MongoClient(host)
        else:
            if port:
                client = MongoClient(host, int(port))
            else:
                client = MongoClient(host)

        database = client[db_name]

        return database[collection_name]

    def get_movies_from_mongo(self, collection, limit, retry_checked):
        poster_empty_query = {
            "$or": [
                {"poster_url": None},
                {"poster_url": ""},
                {"poster_url": {"$exists": False}},
            ]
        }

        if retry_checked:
            query = poster_empty_query
        else:
            query = {
                "$and": [
                    poster_empty_query,
                    {
                        "$or": [
                            {"poster_checked": False},
                            {"poster_checked": {"$exists": False}},
                        ]
                    },
                ]
            }

        projection = {
            "_id": 1,
            "tconst": 1,
            "primaryTitle": 1,
            "startYear": 1,
            "averageRating": 1,
            "numVotes": 1,
            "poster_url": 1,
            "poster_checked": 1,
            "poster_source": 1,
        }

        movies = list(
            collection.find(query, projection)
            .sort([
                ("numVotes", -1),
                ("averageRating", -1),
                ("startYear", -1),
            ])
            .limit(limit)
        )

        return movies

    def update_movie(self, collection, movie, update_data):
        tconst = movie.get("tconst")
        mongo_id = movie.get("_id")

        result = None

        if tconst:
            result = collection.update_one(
                {"tconst": tconst},
                {"$set": update_data},
            )

        if result is None or result.matched_count == 0:
            collection.update_one(
                {"_id": mongo_id},
                {"$set": update_data},
            )

    def get_poster_by_tmdb_pipeline(
        self,
        imdb_id,
        title,
        start_year,
        tmdb_api_key,
    ):
        poster_url = self.get_poster_from_tmdb_find(
            imdb_id=imdb_id,
            api_key=tmdb_api_key,
        )

        if poster_url:
            return poster_url, "tmdb_find"

        poster_url = self.get_poster_from_tmdb_search(
            title=title,
            start_year=start_year,
            api_key=tmdb_api_key,
        )

        if poster_url:
            return poster_url, "tmdb_search"

        return None, "tmdb_not_found"

    def get_poster_from_tmdb_find(self, imdb_id, api_key):
        if not imdb_id:
            return None

        url = f"https://api.themoviedb.org/3/find/{imdb_id}"

        response = requests.get(
            url,
            params={
                "api_key": api_key,
                "external_source": "imdb_id",
                "language": "vi-VN",
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        movie_results = data.get("movie_results") or []
        tv_results = data.get("tv_results") or []

        result = None

        if movie_results:
            result = self.pick_best_tmdb_result(movie_results)
        elif tv_results:
            result = self.pick_best_tmdb_result(tv_results)

        if not result:
            return None

        poster_path = result.get("poster_path")

        if not poster_path:
            return None

        return self.build_tmdb_poster_url(poster_path)

    def get_poster_from_tmdb_search(self, title, start_year, api_key):
        if not title or title == "Không rõ tên":
            return None

        poster_url = self.search_tmdb_movie(
            title=title,
            start_year=start_year,
            api_key=api_key,
        )

        if poster_url:
            return poster_url

        poster_url = self.search_tmdb_tv(
            title=title,
            start_year=start_year,
            api_key=api_key,
        )

        if poster_url:
            return poster_url

        return None

    def search_tmdb_movie(self, title, start_year, api_key):
        url = "https://api.themoviedb.org/3/search/movie"

        params = {
            "api_key": api_key,
            "query": title,
            "language": "vi-VN",
            "include_adult": "false",
        }

        if start_year:
            params["year"] = start_year

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()
        results = data.get("results") or []

        result = self.pick_best_tmdb_result(
            results=results,
            title=title,
            start_year=start_year,
            is_tv=False,
        )

        if not result:
            return None

        poster_path = result.get("poster_path")

        if not poster_path:
            return None

        return self.build_tmdb_poster_url(poster_path)

    def search_tmdb_tv(self, title, start_year, api_key):
        url = "https://api.themoviedb.org/3/search/tv"

        params = {
            "api_key": api_key,
            "query": title,
            "language": "vi-VN",
            "include_adult": "false",
        }

        if start_year:
            params["first_air_date_year"] = start_year

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()
        results = data.get("results") or []

        result = self.pick_best_tmdb_result(
            results=results,
            title=title,
            start_year=start_year,
            is_tv=True,
        )

        if not result:
            return None

        poster_path = result.get("poster_path")

        if not poster_path:
            return None

        return self.build_tmdb_poster_url(poster_path)

    def pick_best_tmdb_result(
        self,
        results,
        title=None,
        start_year=None,
        is_tv=False,
    ):
        if not results:
            return None

        results_with_poster = [
            item for item in results
            if item.get("poster_path")
        ]

        if not results_with_poster:
            return None

        normalized_title = self.normalize_text(title) if title else ""

        def score(item):
            item_score = 0

            item_title = (
                item.get("title")
                or item.get("name")
                or item.get("original_title")
                or item.get("original_name")
                or ""
            )

            item_year = self.extract_year_from_tmdb_result(
                item=item,
                is_tv=is_tv,
            )

            if start_year and item_year and str(start_year) == str(item_year):
                item_score += 50

            if normalized_title:
                normalized_item_title = self.normalize_text(item_title)

                if normalized_item_title == normalized_title:
                    item_score += 40
                elif normalized_title in normalized_item_title:
                    item_score += 20
                elif normalized_item_title in normalized_title:
                    item_score += 15

            popularity = item.get("popularity") or 0

            try:
                item_score += float(popularity)
            except Exception:
                pass

            return item_score

        results_with_poster.sort(key=score, reverse=True)

        return results_with_poster[0]

    def extract_year_from_tmdb_result(self, item, is_tv=False):
        if is_tv:
            raw_date = item.get("first_air_date")
        else:
            raw_date = item.get("release_date")

        if not raw_date:
            return None

        try:
            return int(str(raw_date)[:4])
        except Exception:
            return None

    def build_tmdb_poster_url(self, poster_path):
        if not poster_path:
            return None

        if str(poster_path).startswith("http"):
            return poster_path

        return f"https://image.tmdb.org/t/p/w500{poster_path}"

    def normalize_text(self, value):
        if not value:
            return ""

        return str(value).strip().lower()