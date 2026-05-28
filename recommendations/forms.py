from django import forms
from .models import BookedMovie, UserProfile
from django.forms import DateTimeInput

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class BookMovieForm(forms.ModelForm):
    booking_date = forms.DateTimeField(
        widget=DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )

    class Meta:
        model = BookedMovie
        fields = ['booking_date']


class CustomUserCreationForm(UserCreationForm):
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

    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={
            "placeholder": "Nhập email liên hệ"
        })
    )

    phone_number = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Ví dụ: 0912345678"
        })
    )

    date_of_birth = forms.DateField(
        label="Ngày sinh",
        required=True,
        widget=forms.DateInput(attrs={
            "type": "date"
        })
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

        self.fields["username"].label = "Tên đăng nhập"
        self.fields["username"].help_text = (
            "Tên đăng nhập dùng để đăng nhập vào hệ thống. "
            "Tối đa 150 ký tự. Chỉ gồm chữ cái, số và @ . + - _"
        )

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

        self.fields["username"].widget.attrs.update({
            "placeholder": "Ví dụ: khang123"
        })

        self.fields["password1"].label = "Mật khẩu"
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Nhập mật khẩu"
        })

        self.fields["password2"].label = "Nhập lại mật khẩu"
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Nhập lại mật khẩu"
        })

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()

        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng.")

        return email

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


class UserProfileUpdateForm(forms.Form):
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

    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={
            "placeholder": "Nhập email liên hệ"
        })
    )

    phone_number = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Ví dụ: 0912345678"
        })
    )

    date_of_birth = forms.DateField(
        label="Ngày sinh",
        required=True,
        widget=forms.DateInput(attrs={
            "type": "date"
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

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