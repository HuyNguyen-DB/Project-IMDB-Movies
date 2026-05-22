import time
import requests

from pymongo import MongoClient
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Lấy poster phim từ TMDb theo IMDb ID và lưu trực tiếp vào MongoDB"

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
            help="Thời gian nghỉ giữa mỗi request.",
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
        api_key = getattr(settings, "TMDB_API_KEY", "")

        if not api_key:
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
                self.style.SUCCESS("Không còn phim nào cần cập nhật poster.")
            )
            return

        self.stdout.write(
            self.style.WARNING(f"Bắt đầu kiểm tra poster cho {total} phim...")
        )

        updated_count = 0
        no_poster_count = 0
        error_count = 0

        for index, movie in enumerate(movies, start=1):
            tconst = movie.get("tconst") or movie.get("_id")
            title = movie.get("primaryTitle") or "Không rõ tên"

            if not tconst:
                no_poster_count += 1
                continue

            self.stdout.write(
                f"[{index}/{total}] Đang xử lý: {tconst} - {title}"
            )

            try:
                poster_url = self.get_poster_from_tmdb(tconst, api_key)

                if poster_url:
                    update_data = {
                        "poster_url": poster_url,
                        "poster_checked": True,
                        "poster_updated_at": timezone.now(),
                    }

                    self.update_movie(collection, movie, update_data)

                    updated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  OK: Đã cập nhật poster cho {title}"
                        )
                    )
                else:
                    update_data = {
                        "poster_checked": True,
                        "poster_updated_at": timezone.now(),
                    }

                    self.update_movie(collection, movie, update_data)

                    no_poster_count += 1

                    self.stdout.write(
                        self.style.WARNING(
                            f"  Không tìm thấy poster: {title}"
                        )
                    )

            except requests.RequestException as exc:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(f"  Lỗi request {tconst}: {exc}")
                )

            except Exception as exc:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(f"  Lỗi không xác định {tconst}: {exc}")
                )

            time.sleep(sleep_time)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Hoàn tất cập nhật poster."))
        self.stdout.write(f"Đã cập nhật poster: {updated_count}")
        self.stdout.write(f"Không tìm thấy poster: {no_poster_count}")
        self.stdout.write(f"Lỗi: {error_count}")

    def get_movie_collection(self, collection_name):
        db_config = settings.DATABASES.get("default", {})
        db_name = db_config.get("NAME")

        if not db_name:
            raise Exception("Không tìm thấy NAME trong DATABASES['default'].")

        client_config = db_config.get("CLIENT", {})
        host = client_config.get("host") or client_config.get("HOST") or "mongodb://localhost:27017/"
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
                {"$set": update_data}
            )

        if result is None or result.matched_count == 0:
            collection.update_one(
                {"_id": mongo_id},
                {"$set": update_data}
            )

    def get_poster_from_tmdb(self, imdb_id, api_key):
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
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        movie_results = data.get("movie_results") or []
        tv_results = data.get("tv_results") or []

        result = None

        if movie_results:
            result = movie_results[0]
        elif tv_results:
            result = tv_results[0]

        if not result:
            return None

        poster_path = result.get("poster_path")

        if not poster_path:
            return None

        return f"https://image.tmdb.org/t/p/w500{poster_path}"