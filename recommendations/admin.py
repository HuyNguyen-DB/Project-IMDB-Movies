from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.models import Group

from .models import BookedMovie, Movie, ScreenRoom, RoomImage, Invoice


admin.site.site_header = "Movie Webapp Admin"
admin.site.site_title = "Movie Webapp Admin"
admin.site.index_title = "Bảng điều khiển quản trị"

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


def format_money(value):
    if value is None:
        return "Chưa có giá"
    return f"{value:,} VND"


def format_datetime_vi(value):
    if not value:
        return "Chưa có thời gian"

    try:
        value = timezone.localtime(value)
    except Exception:
        pass

    return value.strftime("%H:%M, %d/%m/%Y")


def badge(text, color):
    color_map = {
        "green": ("rgba(34,197,94,0.14)", "#86efac", "rgba(34,197,94,0.35)"),
        "yellow": ("rgba(250,204,21,0.14)", "#fde68a", "rgba(250,204,21,0.35)"),
        "red": ("rgba(239,68,68,0.14)", "#fca5a5", "rgba(239,68,68,0.35)"),
        "blue": ("rgba(59,130,246,0.14)", "#93c5fd", "rgba(59,130,246,0.35)"),
        "gray": ("rgba(148,163,184,0.14)", "#cbd5e1", "rgba(148,163,184,0.35)"),
        "orange": ("rgba(249,115,22,0.14)", "#fdba74", "rgba(249,115,22,0.35)"),
    }

    bg, text_color, border = color_map.get(color, color_map["gray"])

    return format_html(
        '<span style="display:inline-flex;align-items:center;padding:5px 10px;'
        'border-radius:999px;background:{};color:{};border:1px solid {};'
        'font-size:12px;font-weight:700;white-space:nowrap;">{}</span>',
        bg,
        text_color,
        border,
        text,
    )


class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1
    fields = ("image", "preview_image")
    readonly_fields = ("preview_image",)

    def preview_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:90px;height:60px;object-fit:cover;'
                'border-radius:8px;border:1px solid rgba(255,255,255,0.12);" />',
                obj.image.url
            )
        return "Chưa có ảnh"

    preview_image.short_description = "Xem trước"


@admin.register(BookedMovie)
class BookedMovieAdmin(admin.ModelAdmin):
    list_display = (
        "booking_code",
        "user",
        "movie_title",
        "room_name",
        "booking_date_vi",
        "rental_duration_minutes",
        "total_price_vi",
        "status_badge",
        "payment_badge",
        "invoice_badge",
    )
    def has_add_permission(self, request):
        return False

    list_display_links = ("booking_code", "movie_title")

    list_filter = (
        "status",
        "payment_status",
        "booking_date",
        "date_booked",
        "room_name",
        "movie_genre",
    )

    search_fields = (
        "booking_code",
        "user__username",
        "user__email",
        "movie_title",
        "movie_genre",
        "room_name",
    )

    ordering = ("-date_booked",)
    list_per_page = 25
    save_on_top = True
    date_hierarchy = "booking_date"

    readonly_fields = (
        "booking_code",
        "date_booked",
        "paid_at",
        "total_price",
    )

    fieldsets = (
        ("Thông tin đơn", {
            "fields": (
                "booking_code",
                "user",
                "status",
                "payment_status",
            )
        }),
        ("Thông tin phim", {
            "fields": (
                "movie_title",
                "movie_genre",
            )
        }),
        ("Thông tin phòng chiếu", {
            "fields": (
                "room_name",
                "rental_duration_minutes",
                "price_per_30min",
                "total_price",
            )
        }),
        ("Thời gian", {
            "fields": (
                "booking_date",
                "date_booked",
                "paid_at",
            )
        }),
    )

    actions = (
        "mark_as_paid",
        "mark_as_unpaid",
        "confirm_bookings",
        "cancel_bookings",
    )

    def booking_date_vi(self, obj):
        return format_datetime_vi(obj.booking_date)

    booking_date_vi.short_description = "Ngày giờ xem"
    booking_date_vi.admin_order_field = "booking_date"

    def total_price_vi(self, obj):
        return format_money(obj.total_price)

    total_price_vi.short_description = "Tổng tiền"
    total_price_vi.admin_order_field = "total_price"

    def status_badge(self, obj):
        status_map = {
            "pending": ("Chờ thanh toán", "yellow"),
            "confirmed": ("Đã xác nhận", "green"),
            "cancelled": ("Đã hủy", "red"),
            "expired": ("Hết hạn", "gray"),
        }

        text, color = status_map.get(obj.status, (obj.status, "gray"))
        return badge(text, color)

    status_badge.short_description = "Trạng thái đơn"

    def payment_badge(self, obj):
        if obj.payment_status == "paid":
            return badge("Đã thanh toán", "green")
        if obj.payment_status == "unpaid":
            return badge("Chưa thanh toán", "orange")
        return badge(obj.payment_status, "gray")

    payment_badge.short_description = "Thanh toán"

    def invoice_badge(self, obj):
        try:
            invoice = obj.invoice
            if invoice and invoice.invoice_code:
                return badge(invoice.invoice_code, "blue")
        except Exception:
            pass

        return badge("Chưa có hóa đơn", "gray")

    invoice_badge.short_description = "Hóa đơn"

    def mark_as_paid(self, request, queryset):
        updated = 0
        created_invoice = 0

        for booking in queryset:
            booking.payment_status = "paid"
            booking.status = "confirmed"

            if not booking.paid_at:
                booking.paid_at = timezone.now()

            booking.save()
            updated += 1

            invoice, created = Invoice.objects.get_or_create(
                booking=booking,
                defaults={
                    "user": booking.user,
                    "amount": booking.total_price,
                }
            )

            if created:
                created_invoice += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} đơn sang đã thanh toán. Đã tạo {created_invoice} hóa đơn mới.",
            messages.SUCCESS
        )

    mark_as_paid.short_description = "Xác nhận đã thanh toán và tạo hóa đơn"

    def mark_as_unpaid(self, request, queryset):
        updated = queryset.update(payment_status="unpaid", status="pending", paid_at=None)

        self.message_user(
            request,
            f"Đã chuyển {updated} đơn sang chưa thanh toán.",
            messages.WARNING
        )

    mark_as_unpaid.short_description = "Chuyển về chưa thanh toán"

    def confirm_bookings(self, request, queryset):
        updated = queryset.update(status="confirmed")

        self.message_user(
            request,
            f"Đã xác nhận {updated} đơn đặt phim.",
            messages.SUCCESS
        )

    confirm_bookings.short_description = "Xác nhận đơn"

    def cancel_bookings(self, request, queryset):
        updated = queryset.update(status="cancelled")

        self.message_user(
            request,
            f"Đã hủy {updated} đơn đặt phim.",
            messages.WARNING
        )

    cancel_bookings.short_description = "Hủy đơn"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_code",
        "user",
        "booking_code_display",
        "movie_title_display",
        "amount_vi",
        "created_at_vi",
    )

    def has_add_permission(self, request):
        return False

    list_display_links = ("invoice_code",)
    search_fields = (
        "invoice_code",
        "user__username",
        "user__email",
        "booking__booking_code",
        "booking__movie_title",
    )

    list_filter = (
        "created_at",
        "user",
    )

    ordering = ("-created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"

    readonly_fields = (
        "invoice_code",
        "booking",
        "user",
        "amount",
        "created_at",
    )

    fieldsets = (
        ("Thông tin hóa đơn", {
            "fields": (
                "invoice_code",
                "booking",
                "user",
                "amount",
                "created_at",
            )
        }),
    )

    def booking_code_display(self, obj):
        if obj.booking:
            return obj.booking.booking_code
        return "Không có đơn"

    booking_code_display.short_description = "Mã đơn"

    def movie_title_display(self, obj):
        if obj.booking:
            return obj.booking.movie_title
        return "Không có phim"

    movie_title_display.short_description = "Tên phim"

    def amount_vi(self, obj):
        return format_money(obj.amount)

    amount_vi.short_description = "Số tiền"
    amount_vi.admin_order_field = "amount"

    def created_at_vi(self, obj):
        return format_datetime_vi(obj.created_at)

    created_at_vi.short_description = "Ngày tạo"
    created_at_vi.admin_order_field = "created_at"


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        "poster_preview",
        "primaryTitle",
        "startYear",
        "runtimeMinutes",
        "genres",
        "rating_badge",
        "numVotes",
    )

    list_display_links = ("primaryTitle",)
    search_fields = (
        "tconst",
        "primaryTitle",
        "genres",
    )

    list_filter = (
        "genres",
        "startYear",
    )

    ordering = ("-startYear", "-averageRating")
    list_per_page = 30

    fieldsets = (
        ("Thông tin phim", {
            "fields": (
                "tconst",
                "primaryTitle",
                "startYear",
                "runtimeMinutes",
                "genres",
            )
        }),
        ("Đánh giá", {
            "fields": (
                "averageRating",
                "numVotes",
            )
        }),
        ("Poster", {
            "fields": (
                "poster_url",
            )
        }),
    )

    def poster_preview(self, obj):
        if obj.poster_url:
            return format_html(
                '<img src="{}" style="width:46px;height:68px;object-fit:cover;'
                'border-radius:8px;border:1px solid rgba(255,255,255,0.12);" />',
                obj.poster_url
            )

        return format_html(
            '<div style="width:46px;height:68px;border-radius:8px;background:#111827;'
            'display:flex;align-items:center;justify-content:center;color:#94a3b8;'
            'border:1px solid rgba(255,255,255,0.12);font-size:18px;">🎬</div>'
        )

    poster_preview.short_description = "Poster"

    def rating_badge(self, obj):
        if obj.averageRating is None:
            return badge("Chưa có", "gray")

        if obj.averageRating >= 8:
            return badge(obj.averageRating, "green")

        if obj.averageRating >= 6:
            return badge(obj.averageRating, "yellow")

        return badge(obj.averageRating, "red")

    rating_badge.short_description = "Rating"
    rating_badge.admin_order_field = "averageRating"


@admin.register(ScreenRoom)
class ScreenRoomAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview",
        "room_id",
        "name",
        "room_type_display",
        "formatted_price_per_30min",
        "colored_status",
        "created_at_vi",
    )

    list_display_links = ("room_id", "name")

    search_fields = (
        "room_id",
        "name",
        "description",
    )

    list_filter = (
        "status",
        "created_at",
    )

    ordering = ("room_id",)
    readonly_fields = (
        "created_at",
        "image_preview_large",
    )

    list_per_page = 25
    inlines = [RoomImageInline]

    actions = (
        "set_available",
        "set_maintenance",
        "set_booked",
        "set_price_normal",
        "set_price_vip",
        "set_price_group",
    )

    fieldsets = (
        ("Thông tin phòng", {
            "fields": (
                "room_id",
                "name",
                "description",
                "status",
            )
        }),
        ("Giá thuê", {
            "fields": (
                "price_per_30min",
            )
        }),
        ("Hình ảnh", {
            "fields": (
                "image",
                "image_preview_large",
            )
        }),
        ("Thời gian", {
            "fields": (
                "created_at",
            )
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:70px;height:48px;object-fit:cover;'
                'border-radius:8px;border:1px solid rgba(255,255,255,0.12);" />',
                obj.image.url
            )

        return format_html(
            '<div style="width:70px;height:48px;border-radius:8px;background:#111827;'
            'display:flex;align-items:center;justify-content:center;color:#94a3b8;'
            'border:1px solid rgba(255,255,255,0.12);">🏠</div>'
        )

    image_preview.short_description = "Ảnh"

    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:260px;height:auto;border-radius:14px;'
                'border:1px solid rgba(255,255,255,0.12);" />',
                obj.image.url
            )

        return "Chưa có ảnh"

    image_preview_large.short_description = "Xem trước ảnh"

    def colored_status(self, obj):
        status_map = {
            "available": ("Sẵn sàng", "green"),
            "maintenance": ("Bảo trì", "orange"),
            "booked": ("Đã đặt", "red"),
        }

        text, color = status_map.get(obj.status, (obj.status, "gray"))
        return badge(text, color)

    colored_status.short_description = "Trạng thái"

    def room_type_display(self, obj):
        name = (obj.name or "").lower()

        if "vip" in name:
            return badge("VIP", "blue")

        if "nhóm" in name or "group" in name:
            return badge("Nhóm", "yellow")

        if "thường" in name or "normal" in name:
            return badge("Thường", "green")

        return badge("Khác", "gray")

    room_type_display.short_description = "Loại phòng"

    def formatted_price_per_30min(self, obj):
        return format_money(obj.price_per_30min)

    formatted_price_per_30min.short_description = "Giá / 30 phút"
    formatted_price_per_30min.admin_order_field = "price_per_30min"

    def created_at_vi(self, obj):
        return format_datetime_vi(obj.created_at)

    created_at_vi.short_description = "Ngày tạo"
    created_at_vi.admin_order_field = "created_at"

    def set_available(self, request, queryset):
        updated = queryset.update(status="available")
        self.message_user(request, f"Đã chuyển {updated} phòng sang sẵn sàng.", messages.SUCCESS)

    set_available.short_description = "Chuyển trạng thái: Sẵn sàng"

    def set_maintenance(self, request, queryset):
        updated = queryset.update(status="maintenance")
        self.message_user(request, f"Đã chuyển {updated} phòng sang bảo trì.", messages.WARNING)

    set_maintenance.short_description = "Chuyển trạng thái: Bảo trì"

    def set_booked(self, request, queryset):
        updated = queryset.update(status="booked")
        self.message_user(request, f"Đã chuyển {updated} phòng sang đã đặt.", messages.WARNING)

    set_booked.short_description = "Chuyển trạng thái: Đã đặt"

    def set_price_normal(self, request, queryset):
        updated = queryset.update(price_per_30min=40000)
        self.message_user(request, f"Đã cập nhật {updated} phòng thành 40,000 VND / 30 phút.")

    set_price_normal.short_description = "Đặt giá phòng thường = 40,000 / 30 phút"

    def set_price_vip(self, request, queryset):
        updated = queryset.update(price_per_30min=60000)
        self.message_user(request, f"Đã cập nhật {updated} phòng thành 60,000 VND / 30 phút.")

    set_price_vip.short_description = "Đặt giá phòng VIP = 60,000 / 30 phút"

    def set_price_group(self, request, queryset):
        updated = queryset.update(price_per_30min=90000)
        self.message_user(request, f"Đã cập nhật {updated} phòng thành 90,000 VND / 30 phút.")

    set_price_group.short_description = "Đặt giá phòng nhóm = 90,000 / 30 phút"


@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = (
        "preview_image",
        "room",
        "image",
    )

    list_filter = (
        "room",
    )

    search_fields = (
        "room__room_id",
        "room__name",
    )

    list_per_page = 25

    def preview_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:90px;height:60px;object-fit:cover;'
                'border-radius:8px;border:1px solid rgba(255,255,255,0.12);" />',
                obj.image.url
            )

        return "Chưa có ảnh"

    preview_image.short_description = "Xem trước"