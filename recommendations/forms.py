# =========================================================
# 1. IMPORTS
# - Import form Django
# - Import model cần dùng cho booking và profile
# =========================================================

from django import forms
from django.forms import DateTimeInput
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import BookedMovie, UserProfile


# =========================================================
# 2. BOOKING FORM
# - Form đặt lịch xem phim
# - Người dùng chọn thời gian bắt đầu xem phim
# - Dùng datetime-local để trình duyệt có lịch + giờ
# =========================================================

class BookMovieForm(forms.ModelForm):
    # -----------------------------------------------------
    # 2.1. Thời gian bắt đầu xem
    # - type="datetime-local": cho phép chọn ngày và giờ
    # - class="datetime-input": dùng để CSS/JS tùy chỉnh giao diện
    # - input_formats: định dạng dữ liệu Django nhận từ HTML input
    # -----------------------------------------------------

    booking_date = forms.DateTimeField(
        label="Thời gian bắt đầu xem",
        required=True,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "datetime-input",
                "aria-label": "Thời gian bắt đầu theo định dạng ngày tháng năm giờ phút"
            }
        )
    )

    class Meta:
        model = BookedMovie
        fields = ["booking_date"]


# =========================================================
# 3. SIGNUP FORM
# - Form đăng ký tài khoản
# - Đăng nhập bằng username/password
# - Email chỉ dùng làm thông tin liên hệ
# - Không hiển thị help_text/rule mật khẩu
# =========================================================

class CustomUserCreationForm(UserCreationForm):
    # -----------------------------------------------------
    # 3.1. Thông tin họ tên
    # -----------------------------------------------------

    first_name = forms.CharField(
        label="Họ",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Nhập họ của bạn"
        })
    )

    last_name = forms.CharField(
        label="Tên",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Nhập tên của bạn"
        })
    )

    # -----------------------------------------------------
    # 3.2. Email liên hệ
    # - Email không dùng để đăng nhập
    # - Login vẫn dùng username/password
    # -----------------------------------------------------

    email = forms.EmailField(
        label="Email liên hệ",
        required=True,
        widget=forms.EmailInput(attrs={
            "placeholder": "Nhập email liên hệ"
        })
    )

    # -----------------------------------------------------
    # 3.3. Số điện thoại
    # -----------------------------------------------------

    phone_number = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Ví dụ: 0912345678"
        })
    )

    # -----------------------------------------------------
    # 3.4. Ngày sinh
    # - Vẫn dùng type="date" để trình duyệt có lịch chọn ngày
    # - class="date-input" dùng để CSS/JS hiển thị tiếng Việt
    # -----------------------------------------------------

    date_of_birth = forms.DateField(
        label="Ngày sinh",
        required=True,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "date-input",
                "autocomplete": "bday",
                "aria-label": "Ngày sinh theo định dạng ngày tháng năm"
            }
        )
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "date_of_birth",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # -------------------------------------------------
        # 3.5. Cấu hình label và placeholder cho username
        # -------------------------------------------------

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["username"].help_text = (
            "Tên đăng nhập dùng để đăng nhập vào hệ thống."
        )
        self.fields["username"].widget.attrs.update({
            "placeholder": "Ví dụ: khang123"
        })

        # -------------------------------------------------
        # 3.6. Cấu hình help_text cho thông tin cá nhân
        # -------------------------------------------------

        self.fields["first_name"].help_text = "Nhập họ của bạn."
        self.fields["last_name"].help_text = "Nhập tên của bạn."
        self.fields["email"].help_text = (
            "Email dùng để liên hệ và nhận thông tin tài khoản khi cần."
        )
        self.fields["phone_number"].help_text = (
            "Số điện thoại dùng để liên hệ khi cần xác nhận đơn đặt phim."
        )
        self.fields["date_of_birth"].help_text = (
            "Ngày sinh giúp hệ thống quản lý thông tin tài khoản rõ ràng hơn."
        )

        # -------------------------------------------------
        # 3.7. Cấu hình password
        # - Không hiển thị rule mật khẩu ở giao diện
        # - Backend rule cần được tắt trong settings.py bằng:
        #   AUTH_PASSWORD_VALIDATORS = []
        # -------------------------------------------------

        self.fields["password1"].label = "Mật khẩu"
        self.fields["password1"].help_text = ""
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Nhập mật khẩu"
        })

        self.fields["password2"].label = "Nhập lại mật khẩu"
        self.fields["password2"].help_text = ""
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Nhập lại mật khẩu"
        })

    # -----------------------------------------------------
    # 3.8. Kiểm tra email không bị trùng
    # -----------------------------------------------------

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()

        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng.")

        return email

    # -----------------------------------------------------
    # 3.9. Kiểm tra số điện thoại hợp lệ
    # -----------------------------------------------------

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()

        if not phone_number:
            raise forms.ValidationError("Vui lòng nhập số điện thoại.")

        if not phone_number.isdigit():
            raise forms.ValidationError("Số điện thoại chỉ được chứa chữ số.")

        if len(phone_number) < 9 or len(phone_number) > 11:
            raise forms.ValidationError("Số điện thoại phải có từ 9 đến 11 chữ số.")

        if UserProfile.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("Số điện thoại này đã được sử dụng.")

        return phone_number

    # -----------------------------------------------------
    # 3.10. Lưu User và tạo UserProfile
    # -----------------------------------------------------

    def save(self, commit=True):
        user = super().save(commit=False)

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]

        if commit:
            user.save()

            UserProfile.objects.create(
                user=user,
                phone_number=self.cleaned_data["phone_number"],
                date_of_birth=self.cleaned_data["date_of_birth"]
            )

        return user


# =========================================================
# 4. USER PROFILE UPDATE FORM
# - Form chỉnh sửa thông tin cá nhân
# - Không cho sửa username
# - Email vẫn chỉ là email liên hệ
# =========================================================

class UserProfileUpdateForm(forms.Form):
    # -----------------------------------------------------
    # 4.1. Thông tin họ tên
    # -----------------------------------------------------

    first_name = forms.CharField(
        label="Họ",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Nhập họ của bạn"
        })
    )

    last_name = forms.CharField(
        label="Tên",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Nhập tên của bạn"
        })
    )

    # -----------------------------------------------------
    # 4.2. Email liên hệ
    # -----------------------------------------------------

    email = forms.EmailField(
        label="Email liên hệ",
        required=True,
        widget=forms.EmailInput(attrs={
            "placeholder": "Nhập email liên hệ"
        })
    )

    # -----------------------------------------------------
    # 4.3. Số điện thoại
    # -----------------------------------------------------

    phone_number = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Ví dụ: 0912345678"
        })
    )

    # -----------------------------------------------------
    # 4.4. Ngày sinh trong form chỉnh sửa thông tin cá nhân
    # -----------------------------------------------------

    date_of_birth = forms.DateField(
        label="Ngày sinh",
        required=True,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "date-input",
                "autocomplete": "bday",
                "aria-label": "Ngày sinh theo định dạng ngày tháng năm"
            }
        )
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # -------------------------------------------------
        # 4.5. Đổ dữ liệu hiện tại của user vào form
        # -------------------------------------------------

        if self.user:
            profile = UserProfile.objects.filter(
                user_id=self.user.id
            ).first()

            self.fields["first_name"].initial = self.user.first_name
            self.fields["last_name"].initial = self.user.last_name
            self.fields["email"].initial = self.user.email

            if profile:
                self.fields["phone_number"].initial = profile.phone_number
                self.fields["date_of_birth"].initial = profile.date_of_birth

    # -----------------------------------------------------
    # 4.6. Kiểm tra email không trùng với user khác
    # -----------------------------------------------------

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()

        if not email:
            raise forms.ValidationError("Vui lòng nhập email.")

        if not self.user:
            return email

        existing_user = (
            User.objects
            .filter(email=email)
            .exclude(id=self.user.id)
            .first()
        )

        if existing_user:
            raise forms.ValidationError("Email này đã được sử dụng.")

        return email

    # -----------------------------------------------------
    # 4.7. Kiểm tra số điện thoại không trùng với profile khác
    # -----------------------------------------------------

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()

        if not phone_number:
            raise forms.ValidationError("Vui lòng nhập số điện thoại.")

        if not phone_number.isdigit():
            raise forms.ValidationError("Số điện thoại chỉ được chứa chữ số.")

        if len(phone_number) < 9 or len(phone_number) > 11:
            raise forms.ValidationError("Số điện thoại phải có từ 9 đến 11 chữ số.")

        if not self.user:
            return phone_number

        existing_profile = (
            UserProfile.objects
            .filter(phone_number=phone_number)
            .exclude(user_id=self.user.id)
            .first()
        )

        if existing_profile:
            raise forms.ValidationError("Số điện thoại này đã được sử dụng.")

        return phone_number

    # -----------------------------------------------------
    # 4.8. Lưu thông tin User và UserProfile
    # -----------------------------------------------------

    def save(self):
        user = self.user

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])

        profile = UserProfile.objects.filter(
            user_id=user.id
        ).first()

        if not profile:
            profile = UserProfile.objects.create(
                user=user,
                phone_number="",
                date_of_birth=None
            )

        profile.phone_number = self.cleaned_data["phone_number"]
        profile.date_of_birth = self.cleaned_data["date_of_birth"]
        profile.save(update_fields=["phone_number", "date_of_birth"])

        return user