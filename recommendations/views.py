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
from .models import BookedMovie, Movie, ScreenRoom, Invoice
from .forms import EmailLoginForm, BookMovieForm, CustomUserCreationForm
from django.core.paginator import Paginator

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from django.utils import timezone

# Lấy tất cả dữ liệu phim từ MongoDB và chuyển đổi thành DataFrame
def get_movies():
    movies_queryset = Movie.objects.all()
    movies_data = movies_queryset.values(
        'tconst',
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
    movies = Movie.objects.values(
        'primaryTitle',
        'startYear',
        'runtimeMinutes',
        'genres',
        'poster_url'
    ).order_by('-numVotes')[:5]

    available_rooms = ScreenRoom.objects.filter(
        status='available'
    ).only(
        'room_id',
        'name',
        'description',
        'status',
        'image'
    )

    normal_room = available_rooms.filter(name__icontains='Thường').first()
    vip_room = available_rooms.filter(name__icontains='VIP').first()
    group_room = available_rooms.filter(name__icontains='Nhóm').first()

    featured_rooms = []
    if normal_room:
        featured_rooms.append(normal_room)
    if vip_room:
        featured_rooms.append(vip_room)
    if group_room:
        featured_rooms.append(group_room)

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
            'screen_rooms': featured_rooms,
        }
    )


def room_list(request):
    available_rooms = ScreenRoom.objects.filter(status='available').only(
        'room_id',
        'name',
        'description',
        'status',
        'image'
    )

    normal_rooms = available_rooms.filter(name__icontains='Thường')
    vip_rooms = available_rooms.filter(name__icontains='VIP')
    group_rooms = available_rooms.filter(name__icontains='Nhóm')

    return render(
        request,
        'recommendations/room_list.html',
        {
            'normal_rooms': normal_rooms,
            'vip_rooms': vip_rooms,
            'group_rooms': group_rooms,
        }
    )
# Trang dành cho user đã đăng nhập
@login_required
def user_home(request):
    recommendations = []

    if request.method == 'POST':
        user_genres = request.POST.get('genres', '').strip()
        user_title = request.POST.get('title', '').strip()
        recommendations = recommend(request, user_genres, user_title)

    booked_movies = BookedMovie.objects.filter(user=request.user).order_by('-date_booked')

    return render(request, 'recommendations/user_home.html', {
        'recommendations': recommendations,
        'booked_movies': booked_movies,
    })

# Đăng ký
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)  # ✅ dùng form custom
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()  # ✅ dùng form custom

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
        ['tconst', 'primaryTitle', 'genres', 'averageRating', 'startYear', 'runtimeMinutes','poster_url']
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
        ['tconst', 'primaryTitle', 'genres', 'averageRating', 'startYear', 'runtimeMinutes','poster_url']
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
            .filter(user=request.user, payment_status='paid')
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
    movie_id = request.session.get('selected_movie')
    room_id = request.session.get('selected_room')

    if not movie_id:
        return redirect('movie_list')

    if not room_id:
        return redirect('room_list')

    movie = get_object_or_404(Movie, tconst=movie_id)
    room = get_object_or_404(ScreenRoom, room_id=room_id)

    runtime = movie.runtimeMinutes or 90
    base_duration = round_to_30_minutes(runtime)

    extra_time = int(request.POST.get('extra_time', 0))
    total_duration = base_duration + extra_time

    blocks = total_duration // 30
    total_price = blocks * room.price_per_30min

    if request.method == 'POST':
        form = BookMovieForm(request.POST)

        if form.is_valid():
            booked_movie = form.save(commit=False)

            booked_movie.user = request.user
            booked_movie.movie_title = movie.primaryTitle
            booked_movie.movie_genre = movie.genres
            booked_movie.room_name = room.name
            booked_movie.rental_duration_minutes = total_duration
            booked_movie.price_per_30min = room.price_per_30min
            booked_movie.total_price = total_price

            # NEW
            booked_movie.status = 'pending'
            booked_movie.payment_status = 'unpaid'

            booked_movie.save()

            return redirect('payment_page', booking_id=booked_movie.id)
    else:
        form = BookMovieForm()

    return render(
        request,
        'recommendations/book_movie.html',
        {
            'form': form,
            'movie': movie,
            'room': room,
            'base_duration': base_duration,
            'total_duration': total_duration,
            'total_price': total_price,
        }
    )

@login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(BookedMovie, id=booking_id, user=request.user)

    return render(
        request,
        'recommendations/payment.html',
        {'booking': booking}
    )

@login_required
def confirm_payment(request, booking_id):
    booking = get_object_or_404(BookedMovie, id=booking_id, user=request.user)

    if request.method != 'POST':
        return redirect('payment_page', booking_id=booking.id)

    if booking.payment_status == 'paid':
        messages.warning(request, "Đơn này đã được thanh toán trước đó.")
        if hasattr(booking, 'invoice') and booking.invoice and booking.invoice.invoice_code:
            return redirect('invoice_detail', invoice_code=booking.invoice.invoice_code)
        return redirect('user_home')

    booking.payment_status = 'paid'
    booking.status = 'confirmed'
    booking.paid_at = timezone.now()
    booking.save()

    invoice, created = Invoice.objects.get_or_create(
        booking=booking,
        defaults={
            'user': request.user,
            'amount': booking.total_price
        }
    )

    return redirect('invoice_detail', invoice_code=invoice.invoice_code)

@login_required
def invoice_detail(request, invoice_code):
    invoice = get_object_or_404(
        Invoice,
        invoice_code=invoice_code,
        user=request.user
    )

    return render(
        request,
        'recommendations/invoice_detail.html',
        {'invoice': invoice}
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

def movie_list(request):
    movies = Movie.objects.all().order_by('-startYear')

    paginator = Paginator(movies, 12)  # 12 phim / trang
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'recommendations/movie_list.html', {
        'page_obj': page_obj
    })

@login_required
def handle_booking(request, room_id=None):
    if room_id:
        request.session['selected_room'] = room_id

    movie_id = request.session.get('selected_movie')
    selected_room = request.session.get('selected_room')

    if not movie_id:
        return redirect('movie_list')

    if not selected_room:
        return redirect('room_list')

    return redirect('book_movie')

@login_required
def select_movie(request, movie_id):
    request.session['selected_movie'] = movie_id
    return redirect('handle_booking')

import math

def round_to_30_minutes(minutes):
    try:
        minutes = int(minutes)
        if minutes <= 0:
            minutes = 90
    except (TypeError, ValueError):
        minutes = 90

    return int(math.ceil(minutes / 30.0) * 30)