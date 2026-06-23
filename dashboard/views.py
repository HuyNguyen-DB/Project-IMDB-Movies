from collections import defaultdict
from datetime import date, datetime, time
import json
from urllib.parse import urlencode

from django.contrib import admin
from django.db.models import Count, Sum
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse

from recommendations.models import BookedMovie
from recommendations.admin import (
    get_user_role,
    ROLE_BOOKING_STAFF,
    ROLE_ROOM_STAFF,
    ROLE_SYSTEM_ADMIN,
)

TIMEFRAMES = ["total", "quarter", "day", "month", "year"]


def time_group_key(dt, timeframe):
    if timeframe == "total":
        return "Tổng"

    if timeframe == "quarter":
        quarter_start_month = ((dt.month - 1) // 3) * 3 + 1
        return date(dt.year, quarter_start_month, 1)

    if timeframe == "day":
        return dt.date()

    if timeframe == "month":
        return date(dt.year, dt.month, 1)

    return date(dt.year, 1, 1)


def format_time_label(key, timeframe):
    if timeframe == "total":
        return "Tổng"

    if timeframe == "quarter":
        return f"Q{((key.month - 1) // 3) + 1}/{key.year}"

    if timeframe == "day":
        return key.strftime("%d/%m/%Y")

    if timeframe == "month":
        return key.strftime("%m/%Y")

    return key.strftime("%Y")


def sort_time_keys(keys, timeframe):
    if timeframe == "total":
        return list(keys)

    return sorted(keys)


def build_time_query(key, timeframe):
    if timeframe == "total":
        return {}

    if timeframe == "year":
        return {
            "booking_date__year": key.year,
        }

    if timeframe == "month":
        return {
            "booking_date__year": key.year,
            "booking_date__month": key.month,
        }

    if timeframe == "quarter":
        return {
            "booking_date__year": key.year,
            "booking_date__month__gte": key.month,
            "booking_date__month__lte": key.month + 2,
        }

    if timeframe == "day":
        return {
            "booking_date__year": key.year,
            "booking_date__month": key.month,
            "booking_date__day": key.day,
        }

    return {}

@login_required
def dashboard_view(request):
    role = get_user_role(request.user)

    if role == ROLE_ROOM_STAFF:
        return redirect(reverse("admin:recommendations_screenroom_changelist"))

    if role not in [ROLE_BOOKING_STAFF, ROLE_SYSTEM_ADMIN]:
        return redirect("/admin/")
    
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    timeframe = request.GET.get("timeframe", "total")

    if timeframe not in TIMEFRAMES:
        timeframe = "total"

    filter_kwargs = {}

    if start_date:
        try:
            start_dt = datetime.combine(
                datetime.fromisoformat(start_date).date(),
                time.min,
            )
            filter_kwargs["booking_date__gte"] = start_dt
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.combine(
                datetime.fromisoformat(end_date).date(),
                time.max,
            )
            filter_kwargs["booking_date__lte"] = end_dt
        except ValueError:
            pass

    if filter_kwargs:
        bookings_queryset = BookedMovie.objects.filter(**filter_kwargs).order_by(
            "date_booked"
        )
    else:
        bookings_queryset = BookedMovie.objects.order_by("date_booked")

    total_bookings = bookings_queryset.count()

    total_revenue = (
        bookings_queryset
        .filter(payment_status="paid")
        .aggregate(total=Sum("total_price"))
    )

    confirmed_count = bookings_queryset.filter(
        booking_status="confirmed"
    ).count()

    pending_count = bookings_queryset.filter(
        booking_status="pending_payment"
    ).count()

    cancelled_count = bookings_queryset.filter(
        booking_status="cancelled"
    ).count()

    unpaid_count = bookings_queryset.filter(
        payment_status="unpaid"
    ).count()

    paid_count = bookings_queryset.filter(
        payment_status="paid"
    ).count()

    booking_url = reverse("admin:recommendations_bookedmovie_changelist")
    invoice_url = reverse("admin:recommendations_invoice_changelist")
    room_url = reverse("admin:recommendations_screenroom_changelist")

    # ===== TOP PHIM =====
    top_movies_query = (
        bookings_queryset
        .filter(movie__isnull=False)
        .values("movie__tconst", "movie__primaryTitle")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    movie_labels = [
        item["movie__primaryTitle"] or "Không rõ phim"
        for item in top_movies_query
    ]

    movie_data = [
        item["total"]
        for item in top_movies_query
    ]

    movie_urls = [
        booking_url + "?" + urlencode({
            "movie__tconst__exact": item["movie__tconst"],
        })
        for item in top_movies_query
    ]

    # ===== TOP PHÒNG =====
    top_rooms_query = (
        bookings_queryset
        .exclude(room_name__isnull=True)
        .exclude(room_name="")
        .values("room_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    room_labels = [
        room["room_name"]
        for room in top_rooms_query
    ]

    room_data = [
        room["total"]
        for room in top_rooms_query
    ]

    room_urls = [
        room_url + "?" + urlencode({
            "q": room["room_name"],
        })
        for room in top_rooms_query
    ]

    # ===== THỐNG KÊ THEO THỜI GIAN =====
    time_labels = {}
    time_booking_counts = {}
    time_revenue = {}
    time_payment_paid = {}
    time_payment_unpaid = {}
    time_payment_cancelled = {}

    time_booking_urls = {}
    time_revenue_urls = {}
    time_payment_urls = {}

    for tf in TIMEFRAMES:
        groups_bookings = defaultdict(int)
        groups_revenue = defaultdict(float)
        groups_paid = defaultdict(int)
        groups_unpaid = defaultdict(int)
        groups_cancelled = defaultdict(int)

        for item in bookings_queryset:
            dt = item.date_booked or item.booking_date

            if not dt:
                continue

            key = time_group_key(dt, tf)

            groups_bookings[key] += 1

            if item.booking_status == "cancelled":
                groups_cancelled[key] += 1

            elif item.payment_status == "paid":
                groups_paid[key] += 1
                groups_revenue[key] += float(item.total_price or 0)

            else:
                groups_unpaid[key] += 1

        ordered_keys = sort_time_keys(groups_bookings.keys(), tf)

        time_labels[tf] = [
            format_time_label(k, tf)
            for k in ordered_keys
        ]

        time_booking_counts[tf] = [
            groups_bookings[k]
            for k in ordered_keys
        ]

        time_revenue[tf] = [
            groups_revenue[k]
            for k in ordered_keys
        ]

        time_payment_paid[tf] = [
            groups_paid[k]
            for k in ordered_keys
        ]

        time_payment_unpaid[tf] = [
            groups_unpaid[k]
            for k in ordered_keys
        ]

        time_payment_cancelled[tf] = [
            groups_cancelled[k]
            for k in ordered_keys
        ]

        time_booking_urls[tf] = []
        time_revenue_urls[tf] = []
        time_payment_urls[tf] = []

        for k in ordered_keys:
            query = build_time_query(k, tf)

            booking_query = query.copy()

            revenue_query = query.copy()
            revenue_query["payment_status"] = "paid"

            payment_query = query.copy()

            time_booking_urls[tf].append(
                booking_url + "?" + urlencode(booking_query)
            )

            time_revenue_urls[tf].append(
                booking_url + "?" + urlencode(revenue_query)
            )

            time_payment_urls[tf].append(
                booking_url + "?" + urlencode(payment_query)
            )

    context = {
        "total_bookings": total_bookings,
        "total_revenue": total_revenue["total"] or 0,
        "confirmed_count": confirmed_count,
        "pending_count": pending_count,
        "cancelled_count": cancelled_count,
        "unpaid_count": unpaid_count,
        "paid_count": paid_count,
        "start_date": start_date,
        "end_date": end_date,
        "selected_timeframe": timeframe,

        "movie_labels": json.dumps(movie_labels),
        "movie_data": json.dumps(movie_data),
        "movie_urls": json.dumps(movie_urls),

        "room_labels": json.dumps(room_labels),
        "room_data": json.dumps(room_data),
        "room_urls": json.dumps(room_urls),

        "time_labels": json.dumps(time_labels),
        "time_booking_counts": json.dumps(time_booking_counts),
        "time_revenue": json.dumps(time_revenue),
        "time_payment_paid": json.dumps(time_payment_paid),
        "time_payment_unpaid": json.dumps(time_payment_unpaid),
        "time_payment_cancelled": json.dumps(time_payment_cancelled),

        "time_booking_urls": json.dumps(time_booking_urls),
        "time_revenue_urls": json.dumps(time_revenue_urls),
        "time_payment_urls": json.dumps(time_payment_urls),

        "invoice_url": invoice_url,
        "booking_url": booking_url,
    }

    context.update(admin.site.each_context(request))

    return render(request, "dashboard/index.html", context)