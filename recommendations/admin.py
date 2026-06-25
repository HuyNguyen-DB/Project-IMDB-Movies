from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse, path
from django.http import HttpResponseRedirect

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


# Custom Admin Site với link Dashboard
class CustomAdminSite(admin.AdminSite):
    site_header = "Quản trị Movie Webapp"
    site_title = "Movie Webapp Admin"
    index_title = "Bảng điều khiển quản trị"

    def each_context(self, request):
        context = super().each_context(request)

        role = get_user_role(request.user)

        context["can_view_dashboard"] = role in [
            ROLE_BOOKING_STAFF,
            ROLE_SYSTEM_ADMIN,
        ]

        return context
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_redirect), name='dashboard-redirect'),
        ]
        return custom_urls + urls
    
    def dashboard_redirect(self, request):
        """
        Chỉ nhân viên vận hành và admin tổng được vào dashboard thống kê.
        Các vai trò khác sẽ được đưa về khu vực làm việc phù hợp.
        """
        role = get_user_role(request.user)

        if role in [ROLE_BOOKING_STAFF, ROLE_SYSTEM_ADMIN]:
            return HttpResponseRedirect("/dashboard/")

        if role == ROLE_ROOM_STAFF:
            return HttpResponseRedirect(reverse("admin:recommendations_screenroom_changelist"))

        return HttpResponseRedirect("/admin/")
    
    def index(self, request, extra_context=None):
        """
        Khi vào /admin/ thì chuyển thẳng đến khu vực làm việc
        theo vai trò của tài khoản.
        """
        role = get_user_role(request.user)

        if role == ROLE_BOOKING_STAFF:
            return HttpResponseRedirect(reverse("admin:recommendations_bookedmovie_changelist"))

        if role == ROLE_ROOM_STAFF:
            return HttpResponseRedirect(reverse("admin:recommendations_screenroom_changelist"))

        if role == ROLE_SYSTEM_ADMIN:
            return HttpResponseRedirect(reverse("admin:auth_user_changelist"))

        return super().index(request, extra_context)


# Sử dụng custom admin site
admin.site.__class__ = CustomAdminSite


# =========================================================
# ROLE CONFIG
# =========================================================

ROLE_NORMAL = "normal"
ROLE_ROOM_STAFF = "room_staff"
ROLE_BOOKING_STAFF = "booking_staff"
ROLE_SYSTEM_ADMIN = "system_admin"

ROLE_CHOICES = (
    (ROLE_NORMAL, "Người dùng thường"),
    (ROLE_ROOM_STAFF, "Nhân viên quản lý phòng chiếu"),
    (ROLE_BOOKING_STAFF, "Nhân viên vận hành đặt phim"),
    (ROLE_SYSTEM_ADMIN, "Quản trị hệ thống"),
)


def safe_get_profile(user):
    """
    Lấy UserProfile theo user_id.
    Không dùng user.profile, không dùng get(), không dùng get_or_create()
    để tránh lỗi MultipleObjectsReturned với Djongo/MongoDB.
    """
    if not user or not user.pk:
        return None

    return UserProfile.objects.filter(user_id=user.id).first()


def safe_create_profile(user):
    """
    Tạo UserProfile mới theo model đã dùng user làm primary_key.
    """
    if not user or not user.pk:
        return None

    profile = safe_get_profile(user)

    if profile:
        return profile

    return UserProfile.objects.create(
        user=user,
        phone_number="",
        date_of_birth=None,
        role=ROLE_NORMAL,
    )


def safe_get_or_create_profile(user):
    profile = safe_get_profile(user)

    if profile:
        return profile

    return safe_create_profile(user)


def is_system_admin(user):
    return bool(user and user.is_authenticated and user.is_superuser)


def get_user_role(user):
    if not user or not user.pk:
        return ROLE_NORMAL

    if user.is_superuser:
        return ROLE_SYSTEM_ADMIN

    profile = safe_get_profile(user)

    if profile and profile.role:
        return profile.role

    return ROLE_NORMAL


def is_room_staff(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return get_user_role(user) == ROLE_ROOM_STAFF


def is_booking_staff(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return get_user_role(user) == ROLE_BOOKING_STAFF


def apply_user_role(user, role):
    """
    Gán quyền hệ thống không dùng Group.
    Role nhân viên lưu trong UserProfile.role.
    Quyền vào admin dùng User.is_staff.
    Toàn quyền dùng User.is_superuser.
    """
    profile = safe_get_or_create_profile(user)

    if role == ROLE_SYSTEM_ADMIN:
        if profile:
            profile.role = ROLE_NORMAL
            profile.save(update_fields=["role"])

        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        return

    if role == ROLE_ROOM_STAFF:
        if profile:
            profile.role = ROLE_ROOM_STAFF
            profile.save(update_fields=["role"])

        user.is_staff = True
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])
        return

    if role == ROLE_BOOKING_STAFF:
        if profile:
            profile.role = ROLE_BOOKING_STAFF
            profile.save(update_fields=["role"])

        user.is_staff = True
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])
        return

    if profile:
        profile.role = ROLE_NORMAL
        profile.save(update_fields=["role"])

    user.is_staff = False
    user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])


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
# HIDE DEFAULT GROUP ADMIN
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

    role = forms.ChoiceField(
        label="Vai trò trong hệ thống",
        choices=ROLE_CHOICES,
        required=True,
        help_text=(
            "Chọn vai trò phù hợp. Chỉ Quản trị hệ thống mới được cấp hoặc thay đổi vai trò."
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        user = self.instance

        if user and user.pk:
            profile = safe_get_profile(user)

            if profile:
                self.fields["phone_number"].initial = profile.phone_number
                self.fields["date_of_birth"].initial = profile.date_of_birth
                self.fields["role"].initial = get_user_role(user)
            else:
                self.fields["role"].initial = ROLE_NORMAL

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["first_name"].label = "Họ"
        self.fields["last_name"].label = "Tên"
        self.fields["email"].label = "Email"
        self.fields["is_active"].label = "Kích hoạt tài khoản"

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()

        if not phone_number:
            return phone_number

        if not phone_number.isdigit():
            raise forms.ValidationError("Số điện thoại chỉ được chứa chữ số.")

        if len(phone_number) < 9 or len(phone_number) > 11:
            raise forms.ValidationError("Số điện thoại phải có từ 9 đến 11 chữ số.")

        existing_profile = (
            UserProfile.objects
            .filter(phone_number=phone_number)
            .exclude(user_id=self.instance.id)
            .first()
        )

        if existing_profile:
            raise forms.ValidationError("Số điện thoại này đã được sử dụng.")

        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)

        if commit:
            user.save()

        return user


# =========================================================
# CUSTOM USER ADD FORM
# =========================================================

class CustomUserAddForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput,
        help_text="Mật khẩu nên có ít nhất 8 ký tự, không quá đơn giản và không chỉ gồm số."
    )

    password2 = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput,
        help_text="Nhập lại mật khẩu để xác nhận."
    )

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

    role = forms.ChoiceField(
        label="Vai trò trong hệ thống",
        choices=ROLE_CHOICES,
        initial=ROLE_NORMAL,
        required=True,
        help_text=(
            "Chọn 'Nhân viên quản lý phòng chiếu' hoặc 'Nhân viên vận hành đặt phim' "
            "nếu đây là tài khoản nhân viên."
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["first_name"].label = "Họ"
        self.fields["last_name"].label = "Tên"
        self.fields["email"].label = "Email"
        self.fields["is_active"].label = "Kích hoạt tài khoản"

        self.fields["is_active"].initial = True

        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        self.fields["email"].required = False
        self.fields["is_active"].required = False

        self.fields["username"].help_text = (
            "Bắt buộc. Tối đa 150 ký tự. Chỉ gồm chữ, số và các ký tự @/./+/-/_."
        )

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")

        if not password1:
            raise forms.ValidationError("Vui lòng nhập mật khẩu.")

        if len(password1) < 8:
            raise forms.ValidationError("Mật khẩu phải có ít nhất 8 ký tự.")

        if password1.isdigit():
            raise forms.ValidationError("Mật khẩu không được chỉ gồm số.")

        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if not password2:
            raise forms.ValidationError("Vui lòng nhập lại mật khẩu.")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Hai mật khẩu không khớp.")

        return password2

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
        ).first()

        if existing_profile:
            raise forms.ValidationError("Số điện thoại này đã được sử dụng.")

        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

        return user


# =========================================================
# CUSTOM USER FILTERS
# =========================================================

class AccountTypeFilter(admin.SimpleListFilter):
    title = "Loại tài khoản"
    parameter_name = "account_type"

    def lookups(self, request, model_admin):
        return (
            ("normal", "Người dùng thường"),
            ("room_staff", "Nhân viên quản lý phòng chiếu"),
            ("booking_staff", "Nhân viên vận hành đặt phim"),
            ("superuser", "Quản trị hệ thống"),
        )

    def queryset(self, request, queryset):
        if self.value() == "normal":
            return queryset.filter(
                is_staff=False,
                is_superuser=False
            )

        if self.value() == "room_staff":
            user_ids = list(
                UserProfile.objects
                .filter(role=ROLE_ROOM_STAFF)
                .values_list("user_id", flat=True)
            )

            return queryset.filter(
                id__in=user_ids,
                is_staff=True,
                is_superuser=False
            )

        if self.value() == "booking_staff":
            user_ids = list(
                UserProfile.objects
                .filter(role=ROLE_BOOKING_STAFF)
                .values_list("user_id", flat=True)
            )

            return queryset.filter(
                id__in=user_ids,
                is_staff=True,
                is_superuser=False
            )

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
    add_form = CustomUserAddForm

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
    )

    list_filter = (
        AccountStatusFilter,
        AccountTypeFilter,
        "date_joined",
    )

    ordering = (
        "-date_joined",
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
            "Trạng thái và vai trò",
            {
                "fields": (
                    "is_active",
                    "role",
                ),
                "description": (
                    "Chỉ Quản trị hệ thống được tạo nhân viên và cấp vai trò. "
                    "Không tách riêng vai trò quản lý người dùng vì người dùng tự đăng ký trực tuyến."
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
            "Thông tin tài khoản",
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
        (
            "Thông tin cá nhân",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "date_of_birth",
                ),
            },
        ),
        (
            "Thông tin liên hệ",
            {
                "fields": (
                    "email",
                    "phone_number",
                ),
            },
        ),
        (
            "Trạng thái và vai trò",
            {
                "fields": (
                    "is_active",
                    "role",
                ),
                "description": (
                    "Chọn vai trò cho tài khoản. Nhân viên chỉ được vào những khu vực phù hợp với nghiệp vụ."
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        selected_role = form.cleaned_data.get("role", ROLE_NORMAL)

        obj.save()

        profile = safe_get_or_create_profile(obj)

        if profile:
            profile.phone_number = form.cleaned_data.get("phone_number", "")
            profile.date_of_birth = form.cleaned_data.get("date_of_birth")

            if selected_role == ROLE_SYSTEM_ADMIN:
                profile.role = ROLE_NORMAL
            else:
                profile.role = selected_role

            profile.save()

        apply_user_role(obj, selected_role)

    def has_module_permission(self, request):
        return is_system_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_add_permission(self, request):
        return is_system_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)

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
        profile = safe_get_profile(obj)

        if profile and profile.phone_number:
            return profile.phone_number

        return "Chưa có"

    phone_number_display.short_description = "Số điện thoại"

    def date_of_birth_display(self, obj):
        profile = safe_get_profile(obj)

        if profile and profile.date_of_birth:
            return format_date_vi(profile.date_of_birth)

        return "Chưa có"

    date_of_birth_display.short_description = "Ngày sinh"

    def account_type_display(self, obj):
        role = get_user_role(obj)

        if role == ROLE_SYSTEM_ADMIN:
            return badge("Quản trị hệ thống", "red")

        if role == ROLE_ROOM_STAFF:
            return badge("Nhân viên quản lý phòng chiếu", "blue")

        if role == ROLE_BOOKING_STAFF:
            return badge("Nhân viên vận hành đặt phim", "orange")

        return badge("Người dùng thường", "gray")

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

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_add_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_room_staff(request.user)

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
        "movie_display",
        "room_display",
        "booking_date_vi",
        "booking_end_time_vi",
        "rental_duration_minutes",
        "total_price_vi",
        "booking_status_badge",
        "payment_badge",
        "invoice_badge",
    )

    list_display_links = (
        "booking_code",
        "movie_display",
    )

    list_filter = (
        "booking_status",
        "payment_status",
        "booking_date",
        "date_booked",
        "room",
    )

    search_fields = (
        "booking_code",
        "user__username",
        "user__email",
        "movie__primaryTitle",
        "movie__tconst",
        "room__room_id",
        "room__name",
    )

    ordering = (
        "-booking_date",
        "-date_booked",
    )

    list_per_page = 25
    save_on_top = True

    readonly_fields = (
        "booking_code",
        "user",
        "movie",
        "room",
        "rental_duration_minutes",
        "discount_amount",
        "total_price",
        "booking_date",
        "booking_end_time",
        "date_booked",
        "paid_at",
        "refunded_at",
    )

    fieldsets = (
        (
            "Thông tin đơn",
            {
                "fields": (
                    "booking_code",
                    "user",
                    "booking_status",
                    "payment_status",
                )
            },
        ),
        (
            "Thông tin phim",
            {
                "fields": (
                    "movie",
                )
            },
        ),
        (
            "Thông tin phòng chiếu",
            {
                "fields": (
                    "room_id_snapshot",
                    "room_name",
                    "rental_duration_minutes",
                    "price_per_30min",
                    "discount_amount",
                    "total_price",
                )
            },
        ),
        (
            "Thời gian",
            {
                "fields": (
                    "booking_date",
                    "booking_end_time",
                    "date_booked",
                    "paid_at",
                    "refunded_at",
                )
            },
        ),
    )

    actions = (
        "mark_as_paid",
        "mark_as_unpaid",
        "cancel_bookings",
        "expire_bookings",
    )

    def has_module_permission(self, request):
        return is_system_admin(request.user) or is_booking_staff(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_booking_staff(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_booking_staff(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not (is_system_admin(request.user) or is_booking_staff(request.user)):
            actions.clear()
        return actions

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields

    def movie_display(self, obj):
        if obj.movie:
            return obj.movie.primaryTitle
        return "Không rõ phim"

    movie_display.short_description = "Tên phim"
    movie_display.admin_order_field = "movie__primaryTitle"

    def room_display(self, obj):
        if obj.room:
            return f"{obj.room.room_id} - {obj.room.name}"
        return "Không rõ phòng"

    room_display.short_description = "Phòng chiếu"
    room_display.admin_order_field = "room__name"
    
    def booking_date_vi(self, obj):
        return format_datetime_vi(obj.booking_date)

    booking_date_vi.short_description = "Bắt đầu xem"
    booking_date_vi.admin_order_field = "booking_date"

    def booking_end_time_vi(self, obj):
        return format_datetime_vi(obj.booking_end_time)

    booking_end_time_vi.short_description = "Kết thúc xem"
    booking_end_time_vi.admin_order_field = "booking_end_time"

    def total_price_vi(self, obj):
        return format_money(obj.total_price)

    total_price_vi.short_description = "Tổng tiền"
    total_price_vi.admin_order_field = "total_price"

    def booking_status_badge(self, obj):
        status_map = {
            "pending_payment": ("Chờ thanh toán", "yellow"),
            "confirmed": ("Đã xác nhận", "green"),
            "in_use": ("Đang sử dụng", "blue"),
            "completed": ("Đã hoàn tất", "green"),
            "cancelled": ("Đã hủy", "red"),
            "expired": ("Hết hạn", "gray"),
        }
        text, color = status_map.get(obj.booking_status, (obj.booking_status, "gray"))
        return badge(text, color)

    booking_status_badge.short_description = "Trạng thái đơn"

    def payment_badge(self, obj):
        payment_map = {
            "unpaid": ("Chưa thanh toán", "orange"),
            "paid": ("Đã thanh toán", "green"),
            "refund_pending": ("Chờ hoàn tiền", "yellow"),
            "refunded": ("Đã hoàn tiền", "blue"),
            "failed": ("Thanh toán lỗi", "red"),
        }
        text, color = payment_map.get(obj.payment_status, (obj.payment_status, "gray"))
        return badge(text, color)

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
            booking.booking_status = "confirmed"

            if not booking.paid_at:
                booking.paid_at = timezone.now()

            booking.save()
            updated += 1

            invoice, created = Invoice.objects.get_or_create(
                booking=booking,
                defaults={
                    "user": booking.user,
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
            booking.booking_status = "pending_payment"
            booking.paid_at = None
            booking.save()
            updated += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} đơn sang chưa thanh toán.",
            messages.WARNING,
        )

    mark_as_unpaid.short_description = "Chuyển về chưa thanh toán"

    def cancel_bookings(self, request, queryset):
        updated = 0

        for booking in queryset:
            booking.booking_status = "cancelled"
            booking.save()
            updated += 1

        self.message_user(
            request,
            f"Đã hủy {updated} đơn đặt phim.",
            messages.WARNING,
        )

    cancel_bookings.short_description = "Hủy đơn"

    def expire_bookings(self, request, queryset):
        updated = 0

        for booking in queryset:
            if booking.payment_status == "unpaid":
                booking.booking_status = "expired"
                booking.save()
                updated += 1

        self.message_user(
            request,
            f"Đã chuyển {updated} đơn chưa thanh toán sang hết hạn.",
            messages.WARNING,
        )

    expire_bookings.short_description = "Chuyển đơn chưa thanh toán sang hết hạn"


# =========================================================
# INVOICE ADMIN
# =========================================================

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_code",
        "user",
        "booking_code_display",
        "movie_title",
        "room_name",
        "final_amount_vi",
        "issued_at_vi",
    )

    list_display_links = (
        "invoice_code",
    )

    search_fields = (
        "invoice_code",
        "user__username",
        "user__email",
        "customer_name",
        "customer_email",
        "booking__booking_code",
        "movie_title",
        "room_name",
    )

    list_filter = (
        "issued_at",
        "user",
        "payment_status_at_issue",
    )

    ordering = (
        "-issued_at",
    )

    list_per_page = 25

    readonly_fields = (
        "invoice_code",
        "booking",
        "user",
        "customer_name",
        "customer_email",
        "movie_title",
        "room_name",
        "booking_start_time",
        "booking_end_time",
        "rental_duration_minutes",
        "price_per_30min",
        "discount_amount",
        "final_amount",
        "payment_status_at_issue",
        "issued_at",
    )

    fieldsets = (
        (
            "Thông tin hóa đơn",
            {
                "fields": (
                    "invoice_code",
                    "booking",
                    "user",
                    "customer_name",
                    "customer_email",
                    "payment_status_at_issue",
                    "issued_at",
                )
            },
        ),
        (
            "Thông tin giao dịch tại thời điểm xuất hóa đơn",
            {
                "fields": (
                    "movie_title",
                    "room_name",
                    "booking_start_time",
                    "booking_end_time",
                    "rental_duration_minutes",
                    "price_per_30min",
                    "discount_amount",
                    "final_amount",
                )
            },
        ),
    )

    def has_module_permission(self, request):
        return is_system_admin(request.user) or is_booking_staff(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_booking_staff(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def booking_code_display(self, obj):
        if obj.booking:
            return obj.booking.booking_code
        return "Không có đơn"

    booking_code_display.short_description = "Mã đơn"

    def final_amount_vi(self, obj):
        return format_money(obj.final_amount)

    final_amount_vi.short_description = "Thành tiền"
    final_amount_vi.admin_order_field = "final_amount"

    def issued_at_vi(self, obj):
        return format_datetime_vi(obj.issued_at)

    issued_at_vi.short_description = "Ngày xuất"
    issued_at_vi.admin_order_field = "issued_at"


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
        "primaryTitle",
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
                    "poster_checked",
                    "poster_updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "poster_checked",
        "poster_updated_at",
    )

    def has_module_permission(self, request):
        return is_system_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_add_permission(self, request):
        return is_system_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)

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
        "status",
        "created_at",
        "image_preview_large",
    )

    list_per_page = 25

    inlines = [
        RoomImageInline,
    ]

    actions = (
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
                ),
                "description": (
                    "Trạng thái phòng được hệ thống tự động cập nhật theo luồng đặt phim, "
                    "nhân viên không chỉnh trạng thái thủ công tại đây."
                ),
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

    def has_module_permission(self, request):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_add_permission(self, request):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user) or is_room_staff(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def get_actions(self, request):
        actions = super().get_actions(request)

        if not (is_system_admin(request.user) or is_room_staff(request.user)):
            actions.clear()

        return actions

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