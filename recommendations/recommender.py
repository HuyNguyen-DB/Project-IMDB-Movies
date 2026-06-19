import re
import pandas as pd

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Movie, BookedMovie


# =========================================================
# RECOMMENDER CACHE
# =========================================================

MOVIES_CACHE = None
COUNT_VECTORIZER = None


RECOMMEND_COLUMNS = [
    "tconst",
    "primaryTitle",
    "genres",
    "averageRating",
    "startYear",
    "runtimeMinutes",
    "poster_url",
]


def get_movies_from_db():
    """
    Chỉ lấy các cột cần thiết từ database.
    Hàm này sẽ được cache lại, không gọi DB liên tục mỗi request.
    """
    movies_data = Movie.objects.values(
        "tconst",
        "primaryTitle",
        "genres",
        "averageRating",
        "startYear",
        "runtimeMinutes",
        "poster_url",
    )

    return pd.DataFrame(movies_data)


def load_recommendation_data():
    """
    Load dữ liệu phim và fit CountVectorizer một lần.
    Các request sau sẽ dùng lại cache.
    """
    global MOVIES_CACHE, COUNT_VECTORIZER

    if MOVIES_CACHE is not None and COUNT_VECTORIZER is not None:
        return MOVIES_CACHE, COUNT_VECTORIZER

    movies_df = get_movies_from_db()

    if movies_df.empty or "genres" not in movies_df.columns:
        MOVIES_CACHE = pd.DataFrame()
        COUNT_VECTORIZER = None
        return MOVIES_CACHE, COUNT_VECTORIZER

    movies_df = movies_df.copy()

    movies_df["genres"] = (
        movies_df["genres"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    movies_df["primaryTitle"] = (
        movies_df["primaryTitle"]
        .fillna("")
        .astype(str)
    )

    movies_df["averageRating"] = pd.to_numeric(
        movies_df["averageRating"],
        errors="coerce"
    ).fillna(0)

    count_vectorizer = CountVectorizer(
        tokenizer=lambda value: [
            genre.strip()
            for genre in value.split(",")
            if genre.strip()
        ],
        token_pattern=None
    )

    count_vectorizer.fit(movies_df["genres"])

    MOVIES_CACHE = movies_df
    COUNT_VECTORIZER = count_vectorizer

    return MOVIES_CACHE, COUNT_VECTORIZER


def invalidate_recommendation_cache():
    """
    Gọi hàm này khi bạn import/cập nhật lại dữ liệu phim
    và muốn web load lại dữ liệu mới mà không cần restart server.
    """
    global MOVIES_CACHE, COUNT_VECTORIZER

    MOVIES_CACHE = None
    COUNT_VECTORIZER = None


def get_movie_recommendations(user_genres, num_recommendations=20):
    movies_df, count_vectorizer = load_recommendation_data()

    if movies_df.empty or count_vectorizer is None:
        return pd.DataFrame()

    if not user_genres:
        return pd.DataFrame()

    user_genres = user_genres.lower().strip()

    user_genres_list = [
        genre.strip()
        for genre in user_genres.split(",")
        if genre.strip()
    ]

    if not user_genres_list:
        return pd.DataFrame()

    # Escape để tránh lỗi regex nếu genre có ký tự đặc biệt như sci-fi
    escaped_genres = [
        re.escape(genre)
        for genre in user_genres_list
    ]

    # Match genre theo dạng comma-separated.
    # Ví dụ: drama khớp "drama", "crime,drama", "drama,romance"
    pattern = r"(^|,)\s*(" + "|".join(escaped_genres) + r")\s*(,|$)"

    filtered_movies = movies_df[
        movies_df["genres"].str.contains(
            pattern,
            regex=True,
            na=False
        )
    ].copy()

    if filtered_movies.empty:
        return pd.DataFrame()

    user_vec = count_vectorizer.transform([user_genres])

    genre_matrix_filtered = count_vectorizer.transform(
        filtered_movies["genres"]
    )

    sim_scores = cosine_similarity(
        user_vec,
        genre_matrix_filtered
    )[0]

    filtered_movies["similarity"] = sim_scores

    recommended = filtered_movies.sort_values(
        by=["similarity", "averageRating"],
        ascending=False
    )

    return recommended[RECOMMEND_COLUMNS].head(num_recommendations)


def recommend_movies(user_genres=None, user_title=None, num_recommendations=20):
    movies_df, _ = load_recommendation_data()

    if movies_df.empty:
        return []

    recommendations = pd.DataFrame()

    if user_title:
        title_matches = movies_df[
            movies_df["primaryTitle"].str.contains(
                user_title,
                case=False,
                na=False,
                regex=False
            )
        ]

        recommendations = pd.concat(
            [recommendations, title_matches],
            ignore_index=True
        )

    if user_genres:
        genre_recommendations = get_movie_recommendations(
            user_genres,
            num_recommendations
        )

        recommendations = pd.concat(
            [recommendations, genre_recommendations],
            ignore_index=True
        )

    if recommendations.empty:
        return []

    recommendations = (
        recommendations[RECOMMEND_COLUMNS]
        .drop_duplicates(subset=["tconst"])
    )

    return recommendations.to_dict("records")


def build_user_genres_from_history(user):
    booked_movies = (
        BookedMovie.objects
        .filter(user=user, movie__isnull=False)
        .select_related("movie")
    )

    if not booked_movies.exists():
        return None

    genres = []

    for booking in booked_movies:
        if booking.movie and booking.movie.genres:
            parts = booking.movie.genres.lower().split(",")

            genres.extend([
                genre.strip()
                for genre in parts
                if genre.strip()
            ])

    if not genres:
        return None

    unique_genres = sorted(set(genres))

    return ",".join(unique_genres)