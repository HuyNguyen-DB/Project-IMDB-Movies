import time
import requests

from pymongo import MongoClient
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Lấy poster phim từ OMDb bằng IMDb ID cho các phim còn thiếu poster. "
        "Có kiểm tra URL ảnh trước khi lưu để tránh link Amazon bị Not Found."
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
        omdb_api_key = getattr(settings, "OMDB_API_KEY", "")

        if not omdb_api_key:
            self.stderr.write(
                self.style.ERROR("Thiếu OMDB_API_KEY trong settings.py.")
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
                self.style.SUCCESS("Không còn phim nào cần cập nhật poster bằng OMDb.")
            )
            return

        self.stdout.write(
            self.style.WARNING(f"Bắt đầu kiểm tra poster OMDb cho {total} phim...")
        )

        updated_count = 0
        invalid_url_count = 0
        no_poster_count = 0
        error_count = 0

        for index, movie in enumerate(movies, start=1):
            tconst = movie.get("tconst") or movie.get("_id")
            title = movie.get("primaryTitle") or "Không rõ tên"

            if not tconst:
                no_poster_count += 1
                continue

            self.stdout.write(
                f"[{index}/{total}] Đang xử lý OMDb: {tconst} - {title}"
            )

            try:
                poster_url, poster_status = self.get_poster_from_omdb(
                    imdb_id=tconst,
                    api_key=omdb_api_key,
                )

                if poster_url:
                    update_data = {
                        "poster_url": poster_url,
                        "poster_checked": True,
                        "poster_updated_at": timezone.now(),
                        "poster_source": "omdb",
                    }

                    self.update_movie(collection, movie, update_data)

                    updated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            "  OK: Đã cập nhật poster từ OMDb"
                        )
                    )

                else:
                    source_value = "omdb_not_found"

                    if poster_status == "invalid_image_url":
                        source_value = "omdb_invalid_url"
                        invalid_url_count += 1
                    else:
                        no_poster_count += 1

                    update_data = {
                        "poster_checked": True,
                        "poster_updated_at": timezone.now(),
                        "poster_source": source_value,
                    }

                    self.update_movie(collection, movie, update_data)

                    if poster_status == "invalid_image_url":
                        self.stdout.write(
                            self.style.WARNING(
                                f"  OMDb trả poster nhưng URL ảnh không hợp lệ: {title}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  OMDb không tìm thấy poster: {title}"
                            )
                        )

            except requests.RequestException as exc:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(f"  Lỗi request OMDb {tconst}: {exc}")
                )

            except Exception as exc:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(f"  Lỗi không xác định {tconst}: {exc}")
                )

            time.sleep(sleep_time)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Hoàn tất cập nhật poster bằng OMDb."))
        self.stdout.write(f"Đã cập nhật poster từ OMDb: {updated_count}")
        self.stdout.write(f"OMDb trả URL ảnh lỗi / Not Found: {invalid_url_count}")
        self.stdout.write(f"OMDb không tìm thấy poster: {no_poster_count}")
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
                            {"poster_source": "tmdb_not_found"},
                            {"poster_source": "omdb_invalid_url"},
                            {"poster_source": "omdb_not_found"},
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

    def get_poster_from_omdb(self, imdb_id, api_key):
        if not imdb_id or not api_key:
            return None, "missing_imdb_or_key"

        url = "https://www.omdbapi.com/"

        response = requests.get(
            url,
            params={
                "apikey": api_key,
                "i": imdb_id,
                "plot": "short",
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("Response") != "True":
            return None, "not_found"

        poster_url = data.get("Poster")

        if not poster_url:
            return None, "not_found"

        if poster_url == "N/A":
            return None, "not_found"

        if not self.is_valid_image_url(poster_url):
            return None, "invalid_image_url"

        return poster_url, "ok"

    def is_valid_image_url(self, url):
        if not url:
            return False

        try:
            response = requests.get(
                url,
                timeout=20,
                stream=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36"
                    ),
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )

            content_type = response.headers.get("Content-Type", "")

            is_valid = (
                response.status_code == 200
                and content_type.startswith("image/")
            )

            response.close()

            return is_valid

        except requests.RequestException:
            return False