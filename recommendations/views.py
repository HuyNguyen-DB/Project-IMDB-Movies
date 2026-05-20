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
from django.db.models import Case, When, IntegerField
from .forms import EmailLoginForm, BookMovieForm, CustomUserCreationForm
from django.core.paginator import Paginator

import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from django.utils import timezone
from datetime import timedelta


# Lấy tất cả dữ liệu phim từ MongoDB và chuyển đổi thành DataFrame

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import qrcode
import io
import base64

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

    movies = list(
        Movie.objects.values(
            'primaryTitle',
            'startYear',
            'runtimeMinutes',
            'genres',
            'averageRating',
            'poster_url'
        ).order_by('-numVotes')[:8]
    )

    screen_rooms = list(
        ScreenRoom.objects.filter(
            status='available'
        ).only(
            'room_id',
            'name',
            'description',
            'status',
            'image',
            'price_per_30min'
        ).order_by('room_id')
    )

    # Ưu tiên hiển thị phòng VIP trước, sau đó phòng nhóm, phòng thường.
    def room_priority(room):
        name = (room.name or '').lower()

        if 'vip' in name:
            return 0

        if 'nhóm' in name or 'nhom' in name or 'group' in name:
            return 1

        if 'thường' in name or 'thuong' in name:
            return 2

        return 3

    screen_rooms.sort(
        key=lambda room: (room_priority(room), room.room_id)

    )
    screen_rooms = screen_rooms[:6]


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
            'featured_movie_count': len(movies),
            'featured_room_count': len(screen_rooms),
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
    now = timezone.now()

    # Tự động chuyển đơn chưa thanh toán đã quá ngày giờ xem sang hết hạn.
    BookedMovie.objects.filter(
        user=request.user,
        payment_status='unpaid',
        status='pending',
        booking_date__lt=now
    ).update(
        status='expired'
    )

    if request.method == 'POST':
        user_genres = request.POST.get('genres', '').strip()
        user_title = request.POST.get('title', '').strip()
        recommendations = recommend(request, user_genres, user_title)

    booked_movies = list(
        BookedMovie.objects.filter(user=request.user)
    )

    today = timezone.localtime(now).date()
    tomorrow = today + timedelta(days=1)

    def get_local_date(dt):
        if timezone.is_aware(dt):
            return timezone.localtime(dt).date()
        return dt.date()

    for movie in booked_movies:
        booking_local_date = get_local_date(movie.booking_date)
        movie.is_today = booking_local_date == today
        movie.is_tomorrow = booking_local_date == tomorrow

    paid_movies = [
        movie for movie in booked_movies
        if movie.payment_status == 'paid'
        and movie.status not in ['cancelled', 'expired']
    ]

    unpaid_movies = [
        movie for movie in booked_movies
        if movie.payment_status == 'unpaid'
        and movie.status == 'pending'
        and movie.booking_date >= now
    ]

    cancelled_expired_movies = [
        movie for movie in booked_movies
        if movie.status in ['cancelled', 'expired']
    ]

    sort_option = request.GET.get('sort', 'closest')

    def sort_movies(movie_list):
        if sort_option == 'newest':
            return sorted(
                movie_list,
                key=lambda movie: movie.booking_date,
                reverse=True
            )

        if sort_option == 'oldest':
            return sorted(
                movie_list,
                key=lambda movie: movie.booking_date
            )

        if sort_option == 'price_desc':
            return sorted(
                movie_list,
                key=lambda movie: movie.total_price or 0,
                reverse=True
            )

        if sort_option == 'price_asc':
            return sorted(
                movie_list,
                key=lambda movie: movie.total_price or 0
            )

        # Mặc định: lịch gần hôm nay nhất.
        return sorted(
            movie_list,
            key=lambda movie: abs((movie.booking_date - now).total_seconds())
        )

    paid_movies = sort_movies(paid_movies)
    unpaid_movies = sort_movies(unpaid_movies)
    cancelled_expired_movies = sort_movies(cancelled_expired_movies)

    paid_paginator = Paginator(paid_movies, 4)
    unpaid_paginator = Paginator(unpaid_movies, 3)
    expired_paginator = Paginator(cancelled_expired_movies, 4)

    paid_page_obj = paid_paginator.get_page(request.GET.get('paid_page'))
    unpaid_page_obj = unpaid_paginator.get_page(request.GET.get('unpaid_page'))
    expired_page_obj = expired_paginator.get_page(request.GET.get('expired_page'))

    return render(
        request,
        'recommendations/user_home.html',
        {
            'recommendations': recommendations,

            'paid_movies': paid_page_obj,
            'unpaid_movies': unpaid_page_obj,
            'cancelled_expired_movies': expired_page_obj,

            'paid_total': len(paid_movies),
            'unpaid_total': len(unpaid_movies),
            'expired_total': len(cancelled_expired_movies),

            'total_bookings': len(booked_movies),
            'sort_option': sort_option,
        }
    )
# Đăng ký
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()

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
            return reverse_lazy('admin:index')
        else:
            return reverse_lazy('home')


# Đăng xuất
def custom_logout(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất thành công!")
    return redirect('login')


def custom_login(request):
    if request.method == "POST":
        form = EmailLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
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
        [
            'tconst',
            'primaryTitle',
            'genres',
            'averageRating',
            'startYear',
            'runtimeMinutes',
            'poster_url'
        ]
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
        [
            'tconst',
            'primaryTitle',
            'genres',
            'averageRating',
            'startYear',
            'runtimeMinutes',
            'poster_url'
        ]
    ].drop_duplicates()

    return recommendations.to_dict('records')


# Trang gợi ý phim cho cả guest và user
def recommend_page(request):
    user_genres = None
    user_title = None
    recommendations = []

    if request.method == 'POST':
        user_genres = request.POST.get('genres')
        user_title = request.POST.get('title')

    if not user_genres and not user_title:
        if request.user.is_authenticated:
            user_genres = build_user_genres_from_history(request.user)

            if not user_genres:
                return redirect('choose_genres')
        else:
            return redirect('choose_genres')

    recommendations = recommend(
        request,
        user_genres=user_genres,
        user_title=user_title
    )

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
    Tạo chuỗi genres từ lịch sử đặt phim của user.
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
            booked_movie.movie_poster_url = movie.poster_url
            booked_movie.room_name = room.name
            booked_movie.rental_duration_minutes = total_duration
            booked_movie.price_per_30min = room.price_per_30min
            booked_movie.total_price = total_price

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
    booking = get_object_or_404(
        BookedMovie,
        id=booking_id,
        user=request.user
    )

    now = timezone.now()

    if (
        booking.payment_status == 'unpaid'
        and booking.status == 'pending'
        and booking.booking_date < now
    ):
        booking.status = 'expired'
        booking.save()

    if booking.status == 'expired':
        messages.error(
            request,
            "Đơn đặt phim này đã hết hạn."
        )
        return redirect('user_home')

    # ====== TẠO VIETQR ======

    bank_id = "970422"  # MB Bank
    account_no = "0762535498"  # số tài khoản của bạn
    account_name = "HUY%20NGUYEN"

    amount = int(booking.total_price)

    description = f"BOOKING{booking.id}"

    vietqr_url = (
        f"https://img.vietqr.io/image/"
        f"{bank_id}-{account_no}-compact2.png"
        f"?amount={amount}"
        f"&addInfo={description}"
        f"&accountName={account_name}"
    )

    context = {
        'booking': booking,
        'vietqr_url': vietqr_url,
    }

    return render(
        request,
        'recommendations/payment.html',
        context
    )


@login_required
def confirm_payment(request, booking_id):
    booking = get_object_or_404(BookedMovie, id=booking_id, user=request.user)
    now = timezone.now()

    if request.method != 'POST':
        return redirect('payment_page', booking_id=booking.id)

    if (
        booking.payment_status == 'unpaid'
        and booking.status == 'pending'
        and booking.booking_date < now
    ):
        booking.status = 'expired'
        booking.save()

        messages.error(
            request,
            "Đơn đặt phim này đã hết hạn vì đã qua ngày giờ xem nhưng chưa thanh toán."
        )
        return redirect('user_home')

    if booking.status == 'expired':
        messages.error(
            request,
            "Đơn đặt phim này đã hết hạn nên không thể thanh toán."
        )
        return redirect('user_home')

    if booking.status == 'cancelled':
        messages.error(
            request,
            "Đơn đặt phim này đã bị hủy nên không thể thanh toán."
        )
        return redirect('user_home')

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
    query = request.GET.get('q', '').strip()
    genre = request.GET.get('genre', '').strip()
    year_from = request.GET.get('year_from', '').strip()
    year_to = request.GET.get('year_to', '').strip()
    sort = request.GET.get('sort', 'newest').strip()

    movies = Movie.objects.all()

    if query:
        movies = movies.filter(primaryTitle__icontains=query)

    if genre:
        movies = movies.filter(genres__icontains=genre)

    if year_from:
        try:
            movies = movies.filter(startYear__gte=int(year_from))
        except ValueError:
            year_from = ''

    if year_to:
        try:
            movies = movies.filter(startYear__lte=int(year_to))
        except ValueError:
            year_to = ''

    sort_options = {
        'newest': '-startYear',
        'oldest': 'startYear',
        'rating_desc': '-averageRating',
        'votes_desc': '-numVotes',
        'title_asc': 'primaryTitle',
    }

    movies = movies.order_by(sort_options.get(sort, '-startYear'))

    paginator = Paginator(movies, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    genres = [
        'Action',
        'Adventure',
        'Animation',
        'Biography',
        'Comedy',
        'Crime',
        'Drama',
        'Family',
        'Fantasy',
        'History',
        'Horror',
        'Mystery',
        'Romance',
        'Sci-Fi',
        'Thriller',
        'War',
    ]

    return render(
        request,
        'recommendations/movie_list.html',
        {
            'page_obj': page_obj,
            'query': query,
            'genre': genre,
            'year_from': year_from,
            'year_to': year_to,
            'sort': sort,
            'genres': genres,
            'total_results': paginator.count,
        }
    )


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


@csrf_exempt
def chatbot_api(request):

    if request.method == "POST":

        user_message = request.POST.get("message")

        response = requests.post(
            "https://baton-sweat-levers.ngrok-free.dev/chat",
            json={
                "message": user_message
            }
        )

        data = response.json()

        return JsonResponse({
            "reply": data["response"]
        })

    return JsonResponse({
        "reply": "Invalid request"
    })