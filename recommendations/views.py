from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.forms import AuthenticationForm

from datetime import timedelta
import math
import requests
import pandas as pd
import json

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

from .recommender import (
    recommend_movies,
    build_user_genres_from_history,
)

from .models import (
    BookedMovie,
    Movie,
    ScreenRoom,
    Invoice,
    UserProfile,
)

from .forms import (
    BookMovieForm,
    CustomUserCreationForm,
    UserProfileUpdateForm,
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_display_name(user):
    if not user:
        return ""

    full_name = user.get_full_name().strip()

    if full_name:
        return full_name

    return user.username


def get_or_create_user_profile(user):
    profile = UserProfile.objects.filter(user_id=user.id).first()

    if profile:
        return profile

    return UserProfile.objects.create(
        user=user,
        phone_number="",
        date_of_birth=None,
    )


def round_to_30_minutes(minutes):
    try:
        minutes = int(minutes)

        if minutes <= 0:
            minutes = 90

    except (TypeError, ValueError):
        minutes = 90

    return int(math.ceil(minutes / 30.0) * 30)


def get_movies():
    movies_queryset = Movie.objects.all()

    movies_data = movies_queryset.values(
        "tconst",
        "primaryTitle",
        "genres",
        "averageRating",
        "startYear",
        "runtimeMinutes",
        "poster_url",
    )

    return pd.DataFrame(movies_data)


def build_invoice_defaults(booking):
    user = booking.user

    customer_name = get_display_name(user)
    customer_email = user.email or ""

    if booking.movie:
        movie_title = booking.movie.primaryTitle
    else:
        movie_title = "Không rõ phim"

    return {
        "user": user,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "movie_title": movie_title,
        "room_name": booking.room_name,
        "booking_start_time": booking.booking_date,
        "booking_end_time": booking.booking_end_time,
        "rental_duration_minutes": booking.rental_duration_minutes,
        "price_per_30min": booking.price_per_30min,
        "discount_amount": booking.discount_amount or 0,
        "final_amount": booking.total_price,
        "payment_status_at_issue": booking.payment_status,
    }


def create_or_get_invoice(booking):
    invoice, created = Invoice.objects.get_or_create(
        booking=booking,
        defaults=build_invoice_defaults(booking),
    )

    return invoice

def send_payment_success_email(booking, invoice):
    user = booking.user

    if not user.email:
        return

    if booking.movie:
        movie_title = booking.movie.primaryTitle
    else:
        movie_title = "Không rõ phim"

    context = {
        "booking": booking,
        "invoice": invoice,
        "customer_name": get_display_name(user),
        "movie_title": movie_title,
        "total_price": f"{int(booking.total_price):,}".replace(",", "."),
    }

    html_content = render_to_string(
        "recommendations/emails/payment_success.html",
        context
    )

    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=f"Xác nhận thanh toán đơn {booking.booking_code}",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )

    email.attach_alternative(html_content, "text/html")
    email.send()
    
# =========================================================
# HOME / ROOM
# =========================================================

def home(request):
    movies = list(
        Movie.objects.values(
            "tconst",
            "primaryTitle",
            "startYear",
            "runtimeMinutes",
            "genres",
            "averageRating",
            "poster_url",
        ).order_by("-numVotes")[:8]
    )

    screen_rooms = list(
        ScreenRoom.objects.filter(
            status="available"
        ).only(
            "room_id",
            "name",
            "description",
            "status",
            "image",
            "price_per_30min",
        ).order_by("room_id")
    )

    def room_priority(room):
        name = (room.name or "").lower()

        if "vip" in name:
            return 0

        if "nhóm" in name or "nhom" in name or "group" in name:
            return 1

        if "thường" in name or "thuong" in name:
            return 2

        return 3

    screen_rooms.sort(
        key=lambda room: (room_priority(room), room.room_id)
    )

    screen_rooms = screen_rooms[:6]

    return render(
        request,
        "recommendations/home.html",
        {
            "movies": movies,
            "screen_rooms": screen_rooms,
            "featured_movie_count": len(movies),
            "featured_room_count": len(screen_rooms),
        }
    )


def room_list(request):
    available_rooms = ScreenRoom.objects.filter(
        status="available"
    ).only(
        "room_id",
        "name",
        "description",
        "status",
        "image",
        "price_per_30min",
    )

    normal_rooms = available_rooms.filter(name__icontains="Thường")
    vip_rooms = available_rooms.filter(name__icontains="VIP")
    group_rooms = available_rooms.filter(name__icontains="Nhóm")

    return render(
        request,
        "recommendations/room_list.html",
        {
            "normal_rooms": normal_rooms,
            "vip_rooms": vip_rooms,
            "group_rooms": group_rooms,
        }
    )


def room_detail(request, room_id):
    room = get_object_or_404(ScreenRoom, room_id=room_id)
    images = room.images.all()

    return render(
        request,
        "recommendations/room_detail.html",
        {
            "room": room,
            "images": images,
        }
    )


# =========================================================
# AUTH
# =========================================================

def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Đăng ký tài khoản thành công. Bạn có thể đăng nhập ngay bây giờ."
            )

            return redirect("login")
    else:
        form = CustomUserCreationForm()

    return render(
        request,
        "recommendations/signup.html",
        {
            "form": form,
        }
    )


class CustomLoginView(LoginView):
    template_name = "recommendations/login.html"

    def get_success_url(self):
        if self.request.user.is_staff:
            return reverse_lazy("admin:index")

        return reverse_lazy("home")


def custom_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = AuthenticationForm()

    return render(
        request,
        "recommendations/login.html",
        {
            "form": form,
        }
    )


def custom_logout(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất thành công!")
    return redirect("login")


# =========================================================
# PROFILE
# =========================================================

@login_required
def profile_detail(request):
    profile = get_or_create_user_profile(request.user)

    user_bookings = BookedMovie.objects.filter(user=request.user)
    user_invoices = Invoice.objects.filter(user=request.user)

    profile_stats = {
        "total_bookings": user_bookings.count(),
        "paid_bookings": user_bookings.filter(payment_status="paid").count(),
        "unpaid_bookings": user_bookings.filter(payment_status="unpaid").count(),
        "total_invoices": user_invoices.count(),
    }

    return render(
        request,
        "recommendations/profile_detail.html",
        {
            "profile": profile,
            "profile_stats": profile_stats,
        }
    )


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = UserProfileUpdateForm(
            request.POST,
            user=request.user,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Thông tin cá nhân của bạn đã được cập nhật thành công."
            )

            return redirect("profile_detail")
    else:
        form = UserProfileUpdateForm(
            user=request.user,
        )

    return render(
        request,
        "recommendations/edit_profile.html",
        {
            "form": form,
        }
    )


# =========================================================
# USER HOME / BOOKING HISTORY
# =========================================================

@login_required
def user_home(request):
    now = timezone.now()

    BookedMovie.objects.filter(
        user=request.user,
        payment_status="unpaid",
        booking_status="pending_payment",
        booking_date__lt=now,
    ).update(
        booking_status="expired"
    )

    booked_movies = list(
        BookedMovie.objects
        .filter(user=request.user)
        .select_related("movie")
    )

    today = timezone.localtime(now).date()
    tomorrow = today + timedelta(days=1)

    def get_local_date(dt):
        if timezone.is_aware(dt):
            return timezone.localtime(dt).date()

        return dt.date()

    for booking in booked_movies:
        booking_local_date = get_local_date(booking.booking_date)
        booking.is_today = booking_local_date == today
        booking.is_tomorrow = booking_local_date == tomorrow

    paid_movies = [
        booking for booking in booked_movies
        if booking.payment_status == "paid"
        and booking.booking_status not in ["cancelled", "expired"]
    ]

    unpaid_movies = [
        booking for booking in booked_movies
        if booking.payment_status == "unpaid"
        and booking.booking_status == "pending_payment"
        and booking.booking_date >= now
    ]

    cancelled_expired_movies = [
        booking for booking in booked_movies
        if booking.booking_status in ["cancelled", "expired"]
    ]

    sort_option = request.GET.get("sort", "closest")

    def sort_movies(movie_list):
        if sort_option == "newest":
            return sorted(
                movie_list,
                key=lambda booking: booking.booking_date,
                reverse=True
            )

        if sort_option == "oldest":
            return sorted(
                movie_list,
                key=lambda booking: booking.booking_date
            )

        if sort_option == "price_desc":
            return sorted(
                movie_list,
                key=lambda booking: booking.total_price or 0,
                reverse=True
            )

        if sort_option == "price_asc":
            return sorted(
                movie_list,
                key=lambda booking: booking.total_price or 0
            )

        return sorted(
            movie_list,
            key=lambda booking: abs(
                (booking.booking_date - now).total_seconds()
            )
        )

    paid_movies = sort_movies(paid_movies)
    unpaid_movies = sort_movies(unpaid_movies)
    cancelled_expired_movies = sort_movies(cancelled_expired_movies)

    paid_paginator = Paginator(paid_movies, 4)
    unpaid_paginator = Paginator(unpaid_movies, 3)
    expired_paginator = Paginator(cancelled_expired_movies, 4)

    paid_page_obj = paid_paginator.get_page(
        request.GET.get("paid_page")
    )

    unpaid_page_obj = unpaid_paginator.get_page(
        request.GET.get("unpaid_page")
    )

    expired_page_obj = expired_paginator.get_page(
        request.GET.get("expired_page")
    )

    return render(
        request,
        "recommendations/user_home.html",
        {
            "paid_movies": paid_page_obj,
            "unpaid_movies": unpaid_page_obj,
            "cancelled_expired_movies": expired_page_obj,

            "paid_total": len(paid_movies),
            "unpaid_total": len(unpaid_movies),
            "expired_total": len(cancelled_expired_movies),

            "total_bookings": len(booked_movies),
            "sort_option": sort_option,
        }
    )


# =========================================================
# RECOMMENDATION
# =========================================================

def recommend_page(request):
    user_genres = None
    user_title = None
    recommendations = []

    if request.method == "POST":
        user_genres = request.POST.get("genres", "").strip()
        user_title = request.POST.get("title", "").strip()

    if not user_genres and not user_title:
        if request.user.is_authenticated:
            user_genres = build_user_genres_from_history(request.user)

            if not user_genres:
                return redirect("choose_genres")
        else:
            return redirect("choose_genres")

    recommendations = recommend_movies(
        user_genres=user_genres,
        user_title=user_title,
        num_recommendations=20,
    )

    if request.user.is_authenticated and recommendations:
        paid_movie_ids = set(
            BookedMovie.objects
            .filter(
                user=request.user,
                payment_status="paid",
                movie__isnull=False,
            )
            .values_list("movie_id", flat=True)
        )

        recommendations = [
            movie for movie in recommendations
            if movie["tconst"] not in paid_movie_ids
        ]

    return render(
        request,
        "recommendations/recommend.html",
        {
            "recommendations": recommendations,
        }
    )

def choose_genres(request):
    genres = [
        "action", "adventure", "animation", "biography", "comedy",
        "crime", "documentary", "drama", "family", "fantasy", "film-noir",
        "game-show", "history", "horror", "music", "musical", "mystery",
        "news", "reality-tv", "romance", "sci-fi", "sport", "talk-show",
        "thriller", "war", "western",
    ]

    return render(
        request,
        "recommendations/choose_genres.html",
        {
            "genres": genres,
        }
    )

# =========================================================
# MOVIE LIST
# =========================================================

def movie_list(request):
    query = request.GET.get("q", "").strip()
    genre = request.GET.get("genre", "").strip()
    year_from = request.GET.get("year_from", "").strip()
    year_to = request.GET.get("year_to", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    movies = Movie.objects.all()

    if query:
        movies = movies.filter(primaryTitle__icontains=query)

    if genre:
        movies = movies.filter(genres__icontains=genre)

    if year_from:
        try:
            movies = movies.filter(startYear__gte=int(year_from))
        except ValueError:
            year_from = ""

    if year_to:
        try:
            movies = movies.filter(startYear__lte=int(year_to))
        except ValueError:
            year_to = ""

    sort_options = {
        "newest": "-startYear",
        "oldest": "startYear",
        "rating_desc": "-averageRating",
        "votes_desc": "-numVotes",
        "title_asc": "primaryTitle",
    }

    movies = movies.order_by(
        sort_options.get(sort, "-startYear")
    )

    paginator = Paginator(movies, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    genres = [
        "Action",
        "Adventure",
        "Animation",
        "Biography",
        "Comedy",
        "Crime",
        "Drama",
        "Family",
        "Fantasy",
        "History",
        "Horror",
        "Mystery",
        "Romance",
        "Sci-Fi",
        "Thriller",
        "War",
    ]

    return render(
        request,
        "recommendations/movie_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "genre": genre,
            "year_from": year_from,
            "year_to": year_to,
            "sort": sort,
            "genres": genres,
            "total_results": paginator.count,
        }
    )


# =========================================================
# BOOKING FLOW
# =========================================================

@login_required
def handle_booking(request, room_id=None):
    if room_id:
        request.session["selected_room"] = room_id

    movie_id = request.session.get("selected_movie")
    selected_room = request.session.get("selected_room")

    if not movie_id:
        return redirect("movie_list")

    if not selected_room:
        return redirect("room_list")

    return redirect("book_movie")


@login_required
def select_movie(request, movie_id):
    request.session["selected_movie"] = movie_id
    return redirect("handle_booking")


@login_required
def book_movie(request):
    movie_id = request.session.get("selected_movie")
    room_id = request.session.get("selected_room")

    if not movie_id:
        return redirect("movie_list")

    if not room_id:
        return redirect("room_list")

    movie = get_object_or_404(Movie, tconst=movie_id)
    room = get_object_or_404(ScreenRoom, room_id=room_id)

    runtime = movie.runtimeMinutes or 90
    base_duration = round_to_30_minutes(runtime)

    if request.method == "POST":
        try:
            extra_time = int(request.POST.get("extra_time", 0))
        except (TypeError, ValueError):
            extra_time = 0
    else:
        extra_time = 0

    total_duration = base_duration + extra_time
    blocks = total_duration // 30
    total_price = blocks * room.price_per_30min

    if request.method == "POST":
        form = BookMovieForm(request.POST)

        if form.is_valid():
            booked_movie = form.save(commit=False)

            booked_movie.user = request.user
            booked_movie.movie = movie

            booked_movie.room_id_snapshot = room.room_id
            booked_movie.room_name = room.name

            booked_movie.rental_duration_minutes = total_duration
            booked_movie.price_per_30min = room.price_per_30min
            booked_movie.discount_amount = 0
            booked_movie.total_price = total_price

            booked_movie.booking_status = "pending_payment"
            booked_movie.payment_status = "unpaid"

            booked_movie.save()

            return redirect(
                "payment_page",
                booking_id=booked_movie.id
            )
    else:
        form = BookMovieForm()

    return render(
        request,
        "recommendations/book_movie.html",
        {
            "form": form,
            "movie": movie,
            "room": room,
            "base_duration": base_duration,
            "total_duration": total_duration,
            "total_price": total_price,
        }
    )

# =========================================================
# PAYMENT / SEPAY WEBHOOK / INVOICE FLOW
# =========================================================
# Luồng thanh toán mới:
# 1. Người dùng tạo đơn đặt phim
# 2. Hệ thống chuyển sang payment_page để hiển thị mã QR
# 3. Người dùng chuyển khoản theo đúng nội dung booking_code
# 4. SePay gửi webhook về hệ thống
# 5. Webhook xác nhận số tiền + nội dung chuyển khoản
# 6. Nếu hợp lệ:
#       - booking.payment_status = "paid"
#       - booking.booking_status = "confirmed"
#       - tạo invoice
# 7. Trang payment.html gọi payment_status định kỳ
# 8. Khi thấy paid thì tự chuyển sang invoice_detail
# =========================================================


@csrf_exempt
def sepay_webhook(request):
    # =====================================================
    # 1. SEPAY WEBHOOK
    # - Nhận thông báo thanh toán tự động từ SePay
    # - Không cần người dùng bấm "Tôi đã thanh toán"
    # =====================================================

    print("HEADERS:", dict(request.headers))

    # -----------------------------------------------------
    # 1.1. Chỉ cho phép POST
    # -----------------------------------------------------

    if request.method != "POST":
        return JsonResponse({
            "error": "Invalid method"
        }, status=405)

    # -----------------------------------------------------
    # 1.2. Kiểm tra Authorization từ SePay
    # Lưu ý: sau này nên đưa secret này vào settings.py
    # -----------------------------------------------------

    secret = request.headers.get("Authorization", "")

    expected = "Apikey spsk_live_T6hgYSEssUWqmd7fFQ3kHKMYMk5DmbEx"

    print("SECRET RECEIVED:", secret)
    print("EXPECTED:", expected)

    if secret != expected:
        return JsonResponse({
            "error": "Unauthorized"
        }, status=401)

    try:
        # -------------------------------------------------
        # 1.3. Đọc dữ liệu webhook
        # -------------------------------------------------

        data = json.loads(request.body)

        print("SEPAY WEBHOOK DATA:", data)

        transfer_amount = data.get("transferAmount")
        content = str(data.get("content", "")).strip()

        if not transfer_amount or not content:
            return JsonResponse({
                "error": "Missing payment data"
            }, status=400)

        # -------------------------------------------------
        # 1.4. Tìm đơn chưa thanh toán khớp nội dung CK
        # -------------------------------------------------

        unpaid_bookings = BookedMovie.objects.filter(
            payment_status="unpaid"
        )

        matched_booking = None

        print("TRYING TO MATCH BOOKINGS...")

        for booking in unpaid_bookings:
            booking_code = str(booking.booking_code).strip()
            booking_code_no_hyphen = booking_code.replace("-", "")
            booking_id_pattern = f"BM{booking.id}"

            print(
                f"Checking booking {booking.id}: "
                f"code={booking_code}, "
                f"no_hyphen={booking_code_no_hyphen}, "
                f"pattern={booking_id_pattern}, "
                f"content={content}"
            )

            # Cách 1: nội dung CK chứa booking_code nguyên bản
            if booking_code.lower() in content.lower():
                print(f"MATCHED via booking_code: {booking.id}")
                matched_booking = booking
                break

            # Cách 2: nội dung CK chứa booking_code nhưng bỏ dấu "-"
            if booking_code_no_hyphen.lower() in content.lower():
                print(f"MATCHED via booking_code no hyphen: {booking.id}")
                matched_booking = booking
                break

            # Cách 3: nội dung CK chứa BM + id
            if booking_id_pattern.lower() in content.lower():
                print(f"MATCHED via booking_id_pattern: {booking.id}")
                matched_booking = booking
                break

        if not matched_booking:
            print("NO MATCH FOUND")

            return JsonResponse({
                "success": True,
                "message": "Webhook received but no matching booking"
            })

        print(
            f"MATCHED BOOKING: "
            f"{matched_booking.id} - {matched_booking.booking_code}"
        )

        # -------------------------------------------------
        # 1.5. Kiểm tra số tiền chuyển khoản
        # -------------------------------------------------

        if int(transfer_amount) != int(matched_booking.total_price):
            print(
                f"AMOUNT MISMATCH: "
                f"{transfer_amount} vs {matched_booking.total_price}"
            )

            return JsonResponse({
                "error": "Invalid amount"
            }, status=400)

        # -------------------------------------------------
        # 1.6. Nếu đơn đã paid trước đó thì trả invoice luôn
        # -------------------------------------------------

        if matched_booking.payment_status == "paid":
            print(f"BOOKING {matched_booking.id} ALREADY PAID")

            invoice = create_or_get_invoice(matched_booking)

            return JsonResponse({
                "success": True,
                "message": "Already paid",
                "payment_status": "paid",
                "invoice_code": invoice.invoice_code,
            })

        # -------------------------------------------------
        # 1.7. Cập nhật đơn thành đã thanh toán
        # -------------------------------------------------

        print(f"UPDATING BOOKING {matched_booking.id} TO PAID")

        matched_booking.payment_status = "paid"
        matched_booking.booking_status = "confirmed"
        matched_booking.paid_at = timezone.now()

        matched_booking.save(
            update_fields=[
                "payment_status",
                "booking_status",
                "paid_at",
            ]
        )

        print(f"BOOKING {matched_booking.id} UPDATED SUCCESSFULLY")

        # -------------------------------------------------
        # 1.8. Sau khi paid mới tạo invoice
        # -------------------------------------------------

        invoice = create_or_get_invoice(matched_booking)

        try:
            send_payment_success_email(
                matched_booking,
                invoice
            )
        except Exception as e:
            print("EMAIL ERROR:", e)

        print(f"INVOICE CREATED: {invoice.invoice_code}")

        return JsonResponse({
            "success": True,
            "payment_status": "paid",
            "booking_status": matched_booking.booking_status,
            "invoice_code": invoice.invoice_code,
        })

    except Exception as error:
        print("SEPAY WEBHOOK ERROR:", error)

        return JsonResponse({
            "error": str(error)
        }, status=500)


@login_required
def payment_page(request, booking_id):
    # =====================================================
    # 2. PAYMENT PAGE
    # - Hiển thị trang thanh toán
    # - Chỉ hiển thị QR và thông tin chuyển khoản
    # - Không tạo invoice tại đây nếu chưa thanh toán
    # =====================================================

    booking = get_object_or_404(
        BookedMovie.objects.select_related("movie"),
        id=booking_id,
        user=request.user,
    )

    now = timezone.now()

    # -----------------------------------------------------
    # 2.1. Nếu đơn chưa thanh toán nhưng đã quá giờ xem
    #      thì đánh dấu hết hạn
    # -----------------------------------------------------

    if (
        booking.payment_status == "unpaid"
        and booking.booking_status == "pending_payment"
        and booking.booking_date < now
    ):
        booking.booking_status = "expired"
        booking.save(update_fields=["booking_status"])

    # -----------------------------------------------------
    # 2.2. Chặn đơn hết hạn
    # -----------------------------------------------------

    if booking.booking_status == "expired":
        messages.error(
            request,
            "Đơn đặt phim này đã hết hạn."
        )

        return redirect("user_home")

    # -----------------------------------------------------
    # 2.3. Chặn đơn đã hủy
    # -----------------------------------------------------

    if booking.booking_status == "cancelled":
        messages.error(
            request,
            "Đơn đặt phim này đã bị hủy nên không thể thanh toán."
        )

        return redirect("user_home")

    # -----------------------------------------------------
    # 2.4. Nếu đơn đã thanh toán thì chuyển sang hóa đơn
    # -----------------------------------------------------

    if booking.payment_status == "paid":
        invoice = create_or_get_invoice(booking)

        return redirect(
            "invoice_detail",
            invoice_code=invoice.invoice_code
        )

    # -----------------------------------------------------
    # 2.5. Nếu chưa thanh toán thì tạo QR
    #      Tuyệt đối không tạo invoice ở bước này
    # -----------------------------------------------------

    bank_id = "970422"
    account_no = "0762535498"
    account_name = "HUY%20NGUYEN"

    amount = int(booking.total_price or 0)

    # Nội dung CK phải dễ match với webhook
    description = booking.booking_code or f"BM{booking.id}"

    vietqr_url = (
        f"https://img.vietqr.io/image/"
        f"{bank_id}-{account_no}-compact2.png"
        f"?amount={amount}"
        f"&addInfo={description}"
        f"&accountName={account_name}"
    )

    return render(
        request,
        "recommendations/payment.html",
        {
            "booking": booking,
            "vietqr_url": vietqr_url,
            "payment_check_url": reverse(
                "payment_status",
                kwargs={
                    "booking_id": booking.id
                }
            ),
        }
    )


@login_required
def payment_status(request, booking_id):
    # =====================================================
    # 3. PAYMENT STATUS API
    # - Frontend gọi API này định kỳ
    # - Nếu webhook đã cập nhật paid thì trả invoice_code
    # - Không tự chuyển unpaid thành paid ở đây
    # =====================================================

    booking = get_object_or_404(
        BookedMovie.objects.select_related("movie"),
        id=booking_id,
        user=request.user,
    )

    invoice_code = None

    # -----------------------------------------------------
    # 3.1. Nếu đã paid thì đảm bảo invoice tồn tại
    # -----------------------------------------------------

    if booking.payment_status == "paid":
        invoice = create_or_get_invoice(booking)
        invoice_code = invoice.invoice_code

    # -----------------------------------------------------
    # 3.2. Trả JSON cho payment.html
    # -----------------------------------------------------

    return JsonResponse({
        "payment_status": booking.payment_status,
        "booking_status": booking.booking_status,
        "invoice_code": invoice_code,
    })


@login_required
def invoice_detail(request, invoice_code):
    # =====================================================
    # 4. INVOICE DETAIL
    # - Chỉ hiển thị hóa đơn cho đúng user sở hữu
    # =====================================================

    invoice = get_object_or_404(
        Invoice,
        invoice_code=invoice_code,
        user=request.user,
    )

    return render(
        request,
        "recommendations/invoice_detail.html",
        {
            "invoice": invoice,
        }
    )

# =========================================================
# OTHER
# =========================================================

def some_view(request):
    if not request.user.is_authenticated:
        messages.error(
            request,
            "Bạn cần đăng nhập để thực hiện hành động này."
        )

        return redirect("login")


@csrf_exempt
def chatbot_api(request):
    if request.method == "POST":
        user_message = request.POST.get("message")

        try:
            response = requests.post(
                "https://mutable-usual-endeared.ngrok-free.dev/chat",
                json={
                    "message": user_message
                },
                timeout=30,
            )

            response.raise_for_status()
            data = response.json()

            reply = data.get("response", "Bot chưa có phản hồi.")

            base_url = request.build_absolute_uri("/")[:-1]

            reply = reply.replace(
                "/select_movie/",
                base_url + "/select_movie/"
            )

            #reply = reply.replace(
              #  "/room/",
             #   base_url + "/room/"
            #)

            return JsonResponse({
                "reply": reply
            })

        except Exception as e:
            return JsonResponse({
                "reply": f"Hiện tại chatbot chưa phản hồi được. Lỗi: {str(e)}"
            })

    return JsonResponse({
        "reply": "Invalid request"
    })