from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy

import numpy as np
from .models import BookedMovie, Movie, ScreenRoom
from .forms import EmailLoginForm, BookMovieForm
from django.core.paginator import Paginator

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Lấy tất cả dữ liệu phim từ MongoDB và chuyển đổi thành DataFrame
def get_movies():
    movies_queryset = Movie.objects.all()
    movies_data = movies_queryset.values(
        'primaryTitle',
        'genres',
        'averageRating',
        'startYear',
        'runtimeMinutes',
        'poster_url',   
    )
    return pd.DataFrame(movies_data)


# Trang chủ cho cả user và guest
def home(request):
    recommendations = []

    # Chỉ lấy 5 phim nổi bật
    movies = Movie.objects.values(
        'primaryTitle',
        'startYear',
        'runtimeMinutes',
        'genres',
        'poster_url'
    ).order_by('-numVotes')[:5]
    # Chỉ lấy phòng đang hoạt động
    screen_rooms = ScreenRoom.objects.filter(
        status='available'
    ).only(
        'room_id',
        'name',
        'description',
        'status',
        'image'
    )

    if request.method == 'POST':
        user_genres = request.POST.get('genres', '').strip()
        user_title = request.POST.get('title', '').strip()
        recommendations = recommend(request, user_genres, user_title)

    return render(
        request,
        'recommendations/home.html',
        {
            'movies': movies,
            'recommendations': recommendations,
            'screen_rooms': screen_rooms,
        })
# Trang dành cho user đã đăng nhập
@login_required
def user_home(request):
    recommendations = []

    if request.method == 'POST':
        user_genres = request.POST.get('genres', '').strip()
        user_title = request.POST.get('title', '').strip()
        recommendations = recommend(request, user_genres, user_title)

    # Lấy toàn bộ các phim đã đặt của người dùng
    booked_movies = BookedMovie.objects.filter(user=request.user).order_by('-date_booked')

    return render(request, 'recommendations/user_home.html', {
        'recommendations': recommendations,
        'booked_movies': booked_movies,  # Truyền toàn bộ lịch sử đặt phim
    })


# Đăng ký
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'recommendations/signup.html', {'form': form})

# Đăng nhập
class CustomLoginView(LoginView):
    template_name = 'recommendations/login.html'
    def get_success_url(self):
        """
        Chuyển hướng người dùng đến trang admin nếu là admin,
        hoặc đến trang home nếu là user.
        """
        if self.request.user.is_staff:
            return reverse_lazy('admin:index')  # Chuyển tới trang admin nếu là admin
        else:
            return reverse_lazy('home')  # Chuyển tới trang chủ nếu là người dùng bình thường

# Đăng xuất
def custom_logout(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất thành công!")
    return redirect('login')  # Chuyển hướng về trang đăng nhập

def custom_login(request):
    if request.method == "POST":
        form = EmailLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')  # Redirect về trang chủ sau khi đăng nhập thành công
    else:
        form = EmailLoginForm()
    return render(request, 'recommendations/login.html', {'form': form})

# Hàm recommend gợi ý phim cho cả guest và user
def get_movie_recommendations(user_genres, num_recommendations=20):
    movies_df = get_movies()

    if movies_df.empty or 'genres' not in movies_df.columns:
        return pd.DataFrame()

    movies_df['genres'] = movies_df['genres'].fillna('').str.lower()

    count_vectorizer = CountVectorizer(
        tokenizer=lambda x: [g.strip() for g in x.split(',')]
    )

    count_vectorizer.fit(movies_df['genres'])

    user_genres = user_genres.lower()
    user_vec = count_vectorizer.transform([user_genres])

    genre_matrix = count_vectorizer.transform(movies_df['genres'])

    sim_scores = cosine_similarity(user_vec, genre_matrix)[0]

    movies_df['similarity'] = sim_scores

    recommended = movies_df.sort_values(
        by=['similarity', 'averageRating'],
        ascending=False
    )

    return recommended[
        ['primaryTitle', 'genres', 'averageRating', 'startYear', 'runtimeMinutes','poster_url']
    ].head(num_recommendations)
def recommend(request, user_genres=None, user_title=None):
    movies_df = get_movies()

    if movies_df.empty:
        return []

    recommendations = pd.DataFrame()

    if user_title:
        title_matches = movies_df[
            movies_df['primaryTitle']
            .str.contains(user_title, case=False, na=False)
        ]
        recommendations = pd.concat([recommendations, title_matches])

    if user_genres:
        genre_recommendations = get_movie_recommendations(
            user_genres, 20
        )
        recommendations = pd.concat(
            [recommendations, genre_recommendations]
        )

    if recommendations.empty:
        return render(
            request,
            'recommendations/recommend.html',
            {
                'message': 'Bạn cần nhập tên phim hoặc thể loại',
                'recommendations': []
            }
        )

    recommendations = recommendations[
        ['primaryTitle', 'genres', 'averageRating', 'startYear', 'runtimeMinutes','poster_url']
    ].drop_duplicates()

    return recommendations.to_dict('records')

# Trang gợi ý phim cho cả guest và user
def recommend_page(request):
    user_genres = None
    user_title = None
    recommendations = []

    # 1️⃣ Lấy dữ liệu từ form (nếu có)
    if request.method == 'POST':
        user_genres = request.POST.get('genres')
        user_title = request.POST.get('title')

    # 2️⃣ Nếu KHÔNG có title và genres → thử gợi ý theo lịch sử
    if not user_genres and not user_title:
        if request.user.is_authenticated:
            user_genres = build_user_genres_from_history(request.user)

            # Nếu user đăng nhập nhưng CHƯA có lịch sử
            if not user_genres:
                return redirect('choose_genres')
        else:
            return redirect('choose_genres')

    # 3️⃣ Gọi thuật toán gợi ý hiện có
    recommendations = recommend(
        request,
        user_genres=user_genres,
        user_title=user_title
    )

    # 4️⃣ Nếu có recommendations → loại bỏ phim đã đặt
    if request.user.is_authenticated and recommendations:
        booked_titles = set(
            BookedMovie.objects
            .filter(user=request.user)
            .values_list('movie_title', flat=True)
        )

        recommendations = [
            movie for movie in recommendations
            if movie['primaryTitle'] not in booked_titles
        ]

    return render(
        request,
        'recommendations/recommend.html',
        {'recommendations': recommendations}
    )


def choose_genres(request):
    genres = [
        'action', 'adventure', 'animation', 'biography', 'comedy',
        'crime', 'documentary', 'drama', 'family', 'fantasy', 'film-noir',
        'game-show', 'history', 'horror', 'music', 'musical', 'mystery',
        'news', 'reality-tv', 'romance', 'sci-fi', 'sport', 'talk-show',
        'thriller', 'war', 'western'
    ]

    return render(
        request,
        'recommendations/choose_genres.html',
        {'genres': genres}
    )

def build_user_genres_from_history(user):
    """
    Tạo chuỗi genres từ lịch sử đặt phim của user
    Ví dụ: 'action,thriller,drama'
    """
    booked_movies = BookedMovie.objects.filter(user=user)

    if not booked_movies.exists():
        return None

    genres = []
    for bm in booked_movies:
        if bm.movie_genre:
            parts = bm.movie_genre.lower().split(',')
            genres.extend([g.strip() for g in parts if g.strip()])

    if not genres:
        return None

    # Loại trùng
    unique_genres = list(set(genres))
    return ','.join(unique_genres)
# Đặt phim
@login_required
def book_movie(request):

    title = request.GET.get('title')
    genre = request.GET.get('genre')
    poster = request.GET.get('poster')

    if request.method == 'POST':
        form = BookMovieForm(request.POST)

        if form.is_valid():
            booked_movie = form.save(commit=False)

            booked_movie.user = request.user
            booked_movie.movie_title = title
            booked_movie.movie_genre = genre

            booked_movie.save()

            messages.success(request, "Đặt phim thành công!")
            return redirect('user_home')

    else:
        form = BookMovieForm()

    return render(
        request,
        'recommendations/book_movie.html',
        {
            'form': form,
            'title': title,
            'genre': genre,
            'poster': poster
        }
    )


# Kiểm tra nếu chưa đăng nhập
def some_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "Bạn cần đăng nhập để thực hiện hành động này.")
        return redirect('login')


def room_detail(request, room_id):
    room = get_object_or_404(ScreenRoom, room_id=room_id)
    images = room.images.all()

    return render(
        request,
        'recommendations/room_detail.html',
        {
            'room': room,
            'images': images
        }
    )