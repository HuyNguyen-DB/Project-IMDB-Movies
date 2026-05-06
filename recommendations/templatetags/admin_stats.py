from django import template
from django.utils import timezone
from datetime import timedelta

from recommendations.models import Movie, ScreenRoom, BookedMovie, Invoice


register = template.Library()


def same_local_date(dt, target_date):
    if not dt:
        return False

    try:
        dt = timezone.localtime(dt)
    except Exception:
        pass

    return dt.date() == target_date


@register.simple_tag
def get_admin_stats():
    now = timezone.now()
    today = timezone.localtime(now).date()
    tomorrow = today + timedelta(days=1)

    bookings = list(BookedMovie.objects.all())
    invoices = list(Invoice.objects.all())

    today_bookings = 0
    tomorrow_bookings = 0

    for booking in bookings:
        if same_local_date(booking.booking_date, today):
            today_bookings += 1

        if same_local_date(booking.booking_date, tomorrow):
            tomorrow_bookings += 1

    total_revenue = 0
    for invoice in invoices:
        total_revenue += invoice.amount or 0

    return {
        "total_movies": Movie.objects.count(),
        "total_rooms": ScreenRoom.objects.count(),
        "available_rooms": ScreenRoom.objects.filter(status="available").count(),
        "total_bookings": len(bookings),
        "paid_bookings": len([b for b in bookings if b.payment_status == "paid"]),
        "unpaid_bookings": len([b for b in bookings if b.payment_status == "unpaid"]),
        "today_bookings": today_bookings,
        "tomorrow_bookings": tomorrow_bookings,
        "total_invoices": len(invoices),
        "total_revenue": f"{total_revenue:,} VND",
    }