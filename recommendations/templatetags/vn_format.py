from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def vn_datetime(value):
    if not value:
        return "Chưa cập nhật"

    try:
        value = timezone.localtime(value)
    except Exception:
        pass

    return value.strftime("%H:%M, %d/%m/%Y")


@register.filter
def vn_date(value):
    if not value:
        return "Chưa cập nhật"

    try:
        return value.strftime("%d/%m/%Y")
    except Exception:
        return value


@register.filter
def booking_status_vn(value):
    mapping = {
        "pending_payment": "Chờ thanh toán",
        "confirmed": "Đã xác nhận",
        "in_use": "Đang sử dụng",
        "completed": "Đã hoàn tất",
        "cancelled": "Đã hủy",
        "expired": "Hết hạn",
    }

    return mapping.get(value, value)


@register.filter
def payment_status_vn(value):
    mapping = {
        "unpaid": "Chưa thanh toán",
        "paid": "Đã thanh toán",
        "refund_pending": "Đang chờ hoàn tiền",
        "refunded": "Đã hoàn tiền",
        "failed": "Thanh toán thất bại",
    }

    return mapping.get(value, value)


@register.filter
def room_status_vn(value):
    mapping = {
        "available": "Sẵn sàng",
        "booked": "Đang được đặt",
        "maintenance": "Bảo trì",
        "inactive": "Ngưng sử dụng",
    }

    return mapping.get(value, value)