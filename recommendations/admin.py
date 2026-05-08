from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse

from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from django import forms

from .models import (
    UserProfile,
    BookedMovie,
    Movie,
    ScreenRoom,
    RoomImage,
    Invoice,
)


admin.site.site_header = "Quản trị Movie Webapp"
admin.site.site_title = "Movie Webapp Admin"
admin.site.index_title = "Bảng điều khiển quản trị"


# =========================================================
# HELPER FUNCTIONS
# =========================================================

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


def format_date_vi(value):
    if not value:
        return "Chưa có"

    try:
        return value.strftime("%d/%m/%Y")
    except Exception:
        return value


def badge(text, color):
    color_map = {
        "green": ("#dcfce7", "#166534", "#86efac"),
        "yellow": ("#fef9c3", "#854d0e", "#fde68a"),
        "red": ("#fee2e2", "#991b1b", "#fca5a5"),
        "blue": ("#dbeafe", "#1d4ed8", "#93c5fd"),
        "gray": ("#f1f5f9", "#475569", "#cbd5e1"),
        "orange": ("#ffedd5", "#9a3412", "#fdba74"),
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


# =========================================================
# HIDE GROUPS
# =========================================================

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


# =========================================================
# CUSTOM USER CHANGE FORM
# =========================================================

class CustomUserChangeForm(forms.ModelForm):
    phone_number = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=False,
    )

    date_of_birth = forms.DateField(
        label="Ngày sinh",
        required=False,
        widget=forms.DateInput(attrs={
            "type": "date"
        }),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        user = self.instance

        if user and user.pk:
            try:
                profile = user.profile
                self.fields["phone_number"].initial = profile.phone_number
                self.fields["date_of_birth"].initial = profile.date_of_birth
            except UserProfile.DoesNotExist:
                pass
            except Exception:
                pass

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["first_name"].label = "Họ"
        self.fields["last_name"].label = "Tên"
        self.fields["email"].label = "Email"

        self.fields["is_active"].label = "Kích hoạt tài khoản"
        self.fields["is_staff"].label = "Cho phép vào trang quản trị"
        self.fields["is_superuser"].label = "Toàn quyền quản trị"

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()

        if not phone_number:
            return phone_number

        if not phone_number.isdigit():
            raise forms.ValidationError("Số điện thoại chỉ được chứa chữ số.")

        if len(phone_number) < 9 or len(phone_number) > 11:
            raise forms.ValidationError("Số điện thoại phải có từ 9 đến 11 chữ số.")

        existing_profile = UserProfile.objects.filter(
            phone_number=phone_number
        ).exclude(
            user=self.instance
        ).first()

        if existing_profile:
            raise forms.ValidationError("Số điện thoại này đã được sử dụng.")

        return phone_number

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data.get("phone_number", "")
            profile.date_of_birth = self.cleaned_data.get("date_of_birth")
            profile.save()

        return user


# =========================================================
# CUSTOM USER FILTERS
# =========================================================

class AccountTypeFilter(admin.SimpleListFilter):
    title = "Loại tài khoản"
    parameter_name = "account_type"

    def lookups(self, request, model_admin):
        return (
            ("normal", "Người dùng"),
            ("staff", "Nhân viên admin"),
            ("superuser", "Toàn quyền quản trị"),
        )

    def queryset(self, request, queryset):
        if self.value() == "normal":
            return queryset.filter(is_staff=False, is_superuser=False)

        if self.value() == "staff":
            return queryset.filter(is_staff=True, is_superuser=False)

        if self.value() == "superuser":
            return queryset.filter(is_superuser=True)

        return queryset


class AccountStatusFilter(admin.SimpleListFilter):
    title = "Trạng thái tài khoản"
    parameter_name = "account_status"

    def lookups(self, request, model_admin):
        return (
            ("active", "Đang hoạt động"),
            ("locked", "Đã khóa"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(is_active=True)

        if self.value() == "locked":
            return queryset.filter(is_active=False)

        return queryset


# =========================================================
# CUSTOM USER ADMIN
# =========================================================

class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm

    list_display = (
        "username",
        "email",
        "full_name_display",
        "phone_number_display",
        "date_of_birth_display",
        "account_type_display",
        "is_active_display",
    )

    list_display_links = (
        "username",
        "email",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "profile__phone_number",
    )

    list_filter = (
        AccountStatusFilter,
        AccountTypeFilter,
        "date_joined",
    )

    ordering = (
        "username",
    )

    readonly_fields = (
        "password_change_link",
        "last_login",
        "date_joined",
    )

    fieldsets = (
        (
            "Thông tin tài khoản",
            {
                "fields": (
                    "username",
                    "password_change_link",
                )
            },
        ),
        (
            "Thông tin cá nhân",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "date_of_birth",
                )
            },
        ),
        (
            "Thông tin liên hệ",
            {
                "fields": (
                    "email",
                    "phone_number",
                )
            },
        ),
        (
            "Trạng thái và quyền truy cập",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
                "description": (
                    "Bật 'Cho phép vào trang quản trị' cho tài khoản được phép truy cập admin. "
                    "Bật 'Toàn quyền quản trị' chỉ cho tài khoản quản trị chính."
                ),
            },
        ),
        (
            "Thời gian hệ thống",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    add_fieldsets = (
        (
            "Tạo người dùng mới",
            {
                "classes": (
                    "wide",
                ),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def password_change_link(self, obj):
        if not obj or not obj.pk:
            return "Lưu người dùng trước khi đổi mật khẩu."

        url = reverse("admin:auth_user_password_change", args=[obj.pk])

        return format_html(
            '<a class="button" href="{}" '
            'style="background:#2563eb;color:white;padding:8px 12px;'
            'border-radius:8px;text-decoration:none;font-weight:700;">'
            'Đổi mật khẩu</a>',
            url,
        )

    password_change_link.short_description = "Mật khẩu"

    def full_name_display(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()

        if full_name:
            return full_name

        return "Chưa có"

    full_name_display.short_description = "Họ tên"

    def phone_number_display(self, obj):
        try:
            if obj.profile and obj.profile.phone_number:
                return obj.profile.phone_number
        except Exception:
            pass

        return "Chưa có"

    phone_number_display.short_description = "Số điện thoại"

    def date_of_birth_display(self, obj):
        try:
            if obj.profile and obj.profile.date_of_birth:
                return format_date_vi(obj.profile.date_of_birth)
        except Exception:
            pass

        return "Chưa có"

    date_of_birth_display.short_description = "Ngày sinh"

    def account_type_display(self, obj):
        if obj.is_superuser:
            return badge("Toàn quyền quản trị", "red")

        if obj.is_staff:
            return badge("Nhân viên admin", "blue")

        return badge("Người dùng", "gray")

    account_type_display.short_description = "Loại tài khoản"

    def is_active_display(self, obj):
        if obj.is_active:
            return badge("Đang hoạt động", "green")

        return badge("Đã khóa", "red")

    is_active_display.short_description = "Trạng thái"


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)


# =========================================================
# ROOM IMAGE INLINE
# RoomImage được quản lý trực tiếp trong ScreenRoomAdmin.
# Không đăng ký RoomImageAdmin riêng.
# =========================================================

class RoomImageInline(admin.StackedInline):
    model = RoomImage
    extra = 1
    max_num = 8
    can_delete = True

    fields = (
        "preview_image",
        "image",
    )

    readonly_fields = (
        "preview_image",
    )

    verbose_name = "Ảnh phụ"
    verbose_name_plural = "Ảnh phụ của phòng"

    def preview_image(self, obj):
        if obj and obj.image:
            return format_html(
                '<div style="display:flex;align-items:center;gap:16px;">'
                '<img src="{}" style="width:220px;height:140px;object-fit:cover;'
                'border-radius:14px;border:1px solid #dbe3ef;'
                'box-shadow:0 8px 20px rgba(15,23,42,0.14);" />'
                '<div style="color:#64748b;font-size:13px;line-height:1.5;">'
                '<strong style="color:#334155;">Ảnh hiện tại</strong><br>'
                '{}'
                '</div>'
                '</div>',
                obj.image.url,
                obj.image.name,
            )

        return format_html(
            '<div style="width:220px;height:140px;border-radius:14px;'
            'background:#f8fafc;border:1px dashed #cbd5e1;'
            'display:flex;align-items:center;justify-content:center;'
            'color:#64748b;font-weight:700;">Chưa có ảnh</div>'
        )

    preview_image.short_description = "Xem trước"


# =========================================================
# BOOKED MOVIE ADMIN
# =========================================================

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

    list_display_links = (
        "booking_code",
        "movie_title",
    )

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

    ordering = (
        "-date_booked",
    )

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
        (
            "Thông tin đơn",
            {
                "fields": (
                    "booking_code",
                    "user",
                    "status",
                    "payment_status",
                )
            },
        ),
        (
            "Thông tin phim",
            {
                "fields": (
                    "movie_title",
                    "movie_genre",
                )
            },
        ),
        (
            "Thông tin phòng chiếu",
            {
                "fields": (
                    "room_name",
                    "rental_duration_minutes",
                    "price_per_30min",
                    "total_price",
                )
            },
        ),
        (
            "Thời gian",
            {
                "fields": (
                    "booking_date",
                    "date_booked",
                    "paid_at",
                )
            },
        ),
    )

    actions = (
        "mark_as_paid",
        "mark_as_unpaid",
        "confirm_bookings",
        "cancel_bookings",
    )

    def has_add_permission(self, request):
        return False

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
                },
            )

            if created:
                created_invoice += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} đơn sang đã thanh toán. "
            f"Đã tạo {created_invoice} hóa đơn mới.",
            messages.SUCCESS,
        )

    mark_as_paid.short_description = "Xác nhận đã thanh toán và tạo hóa đơn"

    def mark_as_unpaid(self, request, queryset):
        updated = 0

        for booking in queryset:
            booking.payment_status = "unpaid"
            booking.status = "pending"
            booking.paid_at = None
            booking.save()
            updated += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} đơn sang chưa thanh toán.",
            messages.WARNING,
        )

    mark_as_unpaid.short_description = "Chuyển về chưa thanh toán"

    def confirm_bookings(self, request, queryset):
        updated = 0

        for booking in queryset:
            booking.status = "confirmed"
            booking.save()
            updated += 1

        self.message_user(
            request,
            f"Đã xác nhận {updated} đơn đặt phim.",
            messages.SUCCESS,
        )

    confirm_bookings.short_description = "Xác nhận đơn"

    def cancel_bookings(self, request, queryset):
        updated = 0

        for booking in queryset:
            booking.status = "cancelled"
            booking.save()
            updated += 1

        self.message_user(
            request,
            f"Đã hủy {updated} đơn đặt phim.",
            messages.WARNING,
        )

    cancel_bookings.short_description = "Hủy đơn"


# =========================================================
# INVOICE ADMIN
# =========================================================

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

    list_display_links = (
        "invoice_code",
    )

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

    ordering = (
        "-created_at",
    )

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
        (
            "Thông tin hóa đơn",
            {
                "fields": (
                    "invoice_code",
                    "booking",
                    "user",
                    "amount",
                    "created_at",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

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


# =========================================================
# MOVIE ADMIN
# =========================================================

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

    list_display_links = (
        "primaryTitle",
    )

    search_fields = (
        "tconst",
        "primaryTitle",
        "genres",
    )

    list_filter = (
        "genres",
        "startYear",
    )

    ordering = (
        "-startYear",
        "-averageRating",
    )

    list_per_page = 30

    fieldsets = (
        (
            "Thông tin phim",
            {
                "fields": (
                    "tconst",
                    "primaryTitle",
                    "startYear",
                    "runtimeMinutes",
                    "genres",
                )
            },
        ),
        (
            "Đánh giá",
            {
                "fields": (
                    "averageRating",
                    "numVotes",
                )
            },
        ),
        (
            "Poster",
            {
                "fields": (
                    "poster_url",
                )
            },
        ),
    )

    def poster_preview(self, obj):
        if obj.poster_url:
            return format_html(
                '<img src="{}" style="width:46px;height:68px;object-fit:cover;'
                'border-radius:8px;border:1px solid #dbe3ef;" />',
                obj.poster_url,
            )

        return format_html(
            '<div style="width:46px;height:68px;border-radius:8px;background:#f1f5f9;'
            'display:flex;align-items:center;justify-content:center;color:#64748b;'
            'border:1px solid #dbe3ef;font-size:18px;">🎬</div>'
        )

    poster_preview.short_description = "Poster"

    def rating_badge(self, obj):
        if obj.averageRating is None:
            return badge("Chưa có", "gray")

        try:
            rating = float(obj.averageRating)
        except Exception:
            return badge(obj.averageRating, "gray")

        if rating >= 8:
            return badge(obj.averageRating, "green")

        if rating >= 6:
            return badge(obj.averageRating, "yellow")

        return badge(obj.averageRating, "red")

    rating_badge.short_description = "Điểm"
    rating_badge.admin_order_field = "averageRating"


# =========================================================
# SCREEN ROOM ADMIN
# =========================================================

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

    list_display_links = (
        "room_id",
        "name",
    )

    search_fields = (
        "room_id",
        "name",
        "description",
    )

    list_filter = (
        "status",
        "created_at",
    )

    ordering = (
        "room_id",
    )

    readonly_fields = (
        "created_at",
        "image_preview_large",
    )

    list_per_page = 25

    inlines = [
        RoomImageInline,
    ]

    actions = (
        "set_available",
        "set_maintenance",
        "set_booked",
        "set_price_normal",
        "set_price_vip",
        "set_price_group",
    )

    fieldsets = (
        (
            "Thông tin phòng",
            {
                "fields": (
                    "room_id",
                    "name",
                    "description",
                    "status",
                )
            },
        ),
        (
            "Giá thuê",
            {
                "fields": (
                    "price_per_30min",
                )
            },
        ),
        (
            "Hình ảnh chính",
            {
                "fields": (
                    "image",
                    "image_preview_large",
                )
            },
        ),
        (
            "Thời gian",
            {
                "fields": (
                    "created_at",
                )
            },
        ),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:70px;height:48px;object-fit:cover;'
                'border-radius:8px;border:1px solid #dbe3ef;" />',
                obj.image.url,
            )

        return format_html(
            '<div style="width:70px;height:48px;border-radius:8px;background:#f1f5f9;'
            'display:flex;align-items:center;justify-content:center;color:#64748b;'
            'border:1px solid #dbe3ef;">🏠</div>'
        )

    image_preview.short_description = "Ảnh"

    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:260px;height:auto;border-radius:14px;'
                'border:1px solid #dbe3ef;" />',
                obj.image.url,
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
        updated = 0

        for room in queryset:
            room.status = "available"
            room.save()
            updated += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} phòng sang sẵn sàng.",
            messages.SUCCESS,
        )

    set_available.short_description = "Chuyển trạng thái: Sẵn sàng"

    def set_maintenance(self, request, queryset):
        updated = 0

        for room in queryset:
            room.status = "maintenance"
            room.save()
            updated += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} phòng sang bảo trì.",
            messages.WARNING,
        )

    set_maintenance.short_description = "Chuyển trạng thái: Bảo trì"

    def set_booked(self, request, queryset):
        updated = 0

        for room in queryset:
            room.status = "booked"
            room.save()
            updated += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} phòng sang đã đặt.",
            messages.WARNING,
        )

    set_booked.short_description = "Chuyển trạng thái: Đã đặt"

    def set_price_normal(self, request, queryset):
        updated = 0

        for room in queryset:
            room.price_per_30min = 40000
            room.save()
            updated += 1

        self.message_user(
            request,
            f"Đã cập nhật {updated} phòng thành 40,000 VND / 30 phút.",
            messages.SUCCESS,
        )

    set_price_normal.short_description = "Đặt giá phòng thường = 40,000 / 30 phút"

    def set_price_vip(self, request, queryset):
        updated = 0

        for room in queryset:
            room.price_per_30min = 60000
            room.save()
            updated += 1

        self.message_user(
            request,
            f"Đã cập nhật {updated} phòng thành 60,000 VND / 30 phút.",
            messages.SUCCESS,
        )

    set_price_vip.short_description = "Đặt giá phòng VIP = 60,000 / 30 phút"

    def set_price_group(self, request, queryset):
        updated = 0

        for room in queryset:
            room.price_per_30min = 90000
            room.save()
            updated += 1

        self.message_user(
            request,
            f"Đã cập nhật {updated} phòng thành 90,000 VND / 30 phút.",
            messages.SUCCESS,
        )

    set_price_group.short_description = "Đặt giá phòng nhóm = 90,000 / 30 phút"