from collections import defaultdict
from datetime import date, datetime, time
import json

from django.shortcuts import render
from django.db.models import Count, Sum

from recommendations.models import BookedMovie


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


def dashboard_view(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    timeframe = request.GET.get("timeframe", "total")
    if timeframe not in TIMEFRAMES:
        timeframe = "total"
    filter_kwargs = {}

    if start_date:
        try:
            start_dt = datetime.combine(datetime.fromisoformat(start_date).date(), time.min)
            filter_kwargs["booking_date__gte"] = start_dt
        except ValueError:
            start_dt = None

    if end_date:
        try:
            end_dt = datetime.combine(datetime.fromisoformat(end_date).date(), time.max)
            filter_kwargs["booking_date__lte"] = end_dt
        except ValueError:
            end_dt = None

    bookings_queryset = (
        BookedMovie.objects.filter(**filter_kwargs).order_by("date_booked")
        if filter_kwargs
        else BookedMovie.objects.order_by("date_booked")
    )

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

    # ===== TOP PHIM =====
    top_movies_query = (
        bookings_queryset
        .filter(movie__isnull=False)
        .values("movie__primaryTitle")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    movie_labels = [item["movie__primaryTitle"] or "Không rõ phim" for item in top_movies_query]
    movie_data = [item["total"] for item in top_movies_query]

    # ===== TOP PHÒNG =====
    top_rooms_query = (
        bookings_queryset
        .exclude(room_name__isnull=True)
        .exclude(room_name="")
        .values("room_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    room_labels = [room["room_name"] for room in top_rooms_query]
    room_data = [room["total"] for room in top_rooms_query]

    time_labels = {}
    time_booking_counts = {}
    time_revenue = {}
    time_payment_paid = {}
    time_payment_unpaid = {}
    time_payment_cancelled = {}

    for tf in TIMEFRAMES:
        groups_bookings = defaultdict(int)
        groups_revenue = defaultdict(float)
        groups_paid = defaultdict(int)
        groups_unpaid = defaultdict(int)
        groups_cancelled = defaultdict(int)

        for item in bookings_queryset:
            dt = item.date_booked or item.booking_date
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

        time_labels[tf] = [format_time_label(k, tf) for k in ordered_keys]
        time_booking_counts[tf] = [groups_bookings[k] for k in ordered_keys]
        time_revenue[tf] = [groups_revenue[k] for k in ordered_keys]
        time_payment_paid[tf] = [groups_paid[k] for k in ordered_keys]
        time_payment_unpaid[tf] = [groups_unpaid[k] for k in ordered_keys]
        time_payment_cancelled[tf] = [groups_cancelled[k] for k in ordered_keys]

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

        "room_labels": json.dumps(room_labels),
        "room_data": json.dumps(room_data),

        "time_labels": json.dumps(time_labels),
        "time_booking_counts": json.dumps(time_booking_counts),
        "time_revenue": json.dumps(time_revenue),
        "time_payment_paid": json.dumps(time_payment_paid),
        "time_payment_unpaid": json.dumps(time_payment_unpaid),
        "time_payment_cancelled": json.dumps(time_payment_cancelled),
    }

    return render(request, "dashboard/index.html", context)
