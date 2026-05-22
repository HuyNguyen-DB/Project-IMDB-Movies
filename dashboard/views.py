from collections import defaultdict
from datetime import date
import json

from django.shortcuts import render
from django.db.models import Count, Sum

from recommendations.models import BookedMovie


TIMEFRAMES = ["day", "month", "year"]


def time_group_key(dt, timeframe):
    if timeframe == "day":
        return dt.date()
    if timeframe == "month":
        return date(dt.year, dt.month, 1)
    return date(dt.year, 1, 1)


def format_time_label(key, timeframe):
    if timeframe == "day":
        return key.strftime("%d/%m/%Y")
    if timeframe == "month":
        return key.strftime("%m/%Y")
    return key.strftime("%Y")


def dashboard_view(request):
    total_bookings = BookedMovie.objects.count()

    total_revenue = (
        BookedMovie.objects
        .filter(payment_status="paid")
        .aggregate(total=Sum("total_price"))
    )

    confirmed_count = BookedMovie.objects.filter(
        booking_status="confirmed"
    ).count()

    pending_count = BookedMovie.objects.filter(
        booking_status="pending_payment"
    ).count()

    cancelled_count = BookedMovie.objects.filter(
        booking_status="cancelled"
    ).count()

    unpaid_count = BookedMovie.objects.filter(
        payment_status="unpaid"
    ).count()

    paid_count = BookedMovie.objects.filter(
        payment_status="paid"
    ).count()

    # ===== TOP PHIM =====
    top_movies_query = (
        BookedMovie.objects
        .filter(movie__isnull=False)
        .values("movie__primaryTitle")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    movie_labels = [item["movie__primaryTitle"] or "Không rõ phim" for item in top_movies_query]
    movie_data = [item["total"] for item in top_movies_query]

    # ===== TRẠNG THÁI THANH TOÁN =====
    status_labels = [
        "Chưa Thanh Toán",
        "Đã Thanh Toán",
    ]

    status_data = [
        unpaid_count,
        paid_count,
    ]

    # ===== TOP PHÒNG =====
    top_rooms_query = (
        BookedMovie.objects
        .exclude(room_name__isnull=True)
        .exclude(room_name="")
        .values("room_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    room_labels = [room["room_name"] for room in top_rooms_query]
    room_data = [room["total"] for room in top_rooms_query]

    all_bookings = BookedMovie.objects.order_by("date_booked")

    time_labels = {}
    time_booking_counts = {}
    time_revenue = {}
    time_payment_paid = {}
    time_payment_unpaid = {}

    for timeframe in TIMEFRAMES:
        groups_bookings = defaultdict(int)
        groups_revenue = defaultdict(float)
        groups_paid = defaultdict(int)
        groups_unpaid = defaultdict(int)

        for item in all_bookings:
            dt = item.date_booked or item.booking_date
            key = time_group_key(dt, timeframe)

            groups_bookings[key] += 1

            if item.payment_status == "paid":
                groups_revenue[key] += float(item.total_price or 0)
                groups_paid[key] += 1
            else:
                groups_unpaid[key] += 1

        ordered_keys = sorted(groups_bookings.keys())

        time_labels[timeframe] = [format_time_label(k, timeframe) for k in ordered_keys]
        time_booking_counts[timeframe] = [groups_bookings[k] for k in ordered_keys]
        time_revenue[timeframe] = [groups_revenue[k] for k in ordered_keys]
        time_payment_paid[timeframe] = [groups_paid[k] for k in ordered_keys]
        time_payment_unpaid[timeframe] = [groups_unpaid[k] for k in ordered_keys]

    context = {
        "total_bookings": total_bookings,
        "total_revenue": total_revenue["total"] or 0,
        "confirmed_count": confirmed_count,
        "pending_count": pending_count,
        "cancelled_count": cancelled_count,
        "unpaid_count": unpaid_count,
        "paid_count": paid_count,

        "movie_labels": json.dumps(movie_labels),
        "movie_data": json.dumps(movie_data),

        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),

        "room_labels": json.dumps(room_labels),
        "room_data": json.dumps(room_data),

        "time_labels": json.dumps(time_labels),
        "time_booking_counts": json.dumps(time_booking_counts),
        "time_revenue": json.dumps(time_revenue),
        "time_payment_paid": json.dumps(time_payment_paid),
        "time_payment_unpaid": json.dumps(time_payment_unpaid),
    }

    return render(request, "dashboard/index.html", context)
