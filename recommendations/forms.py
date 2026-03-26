from django import forms
from .models import BookedMovie
from django.forms import DateTimeInput

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

from django.contrib.auth.forms import UserCreationForm


class BookMovieForm(forms.ModelForm):
    class Meta:
        model = BookedMovie
        fields = ['movie_title', 'movie_genre', 'booking_date']  # Thêm trường booking_date

    booking_date = forms.DateTimeField(
        widget=DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M']
    )

class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", max_length=254)

    def clean_username(self):
        email = self.cleaned_data.get("username")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError("Không tìm thấy tài khoản với email này.")
        return email
    
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['username'].help_text = (
            "Tên đăng nhập tối đa 150 ký tự. Chỉ gồm chữ cái, số và @ . + - _"
        )

        self.fields['password1'].help_text = (
            "Mật khẩu phải có ít nhất 8 ký tự, không quá đơn giản và không chỉ gồm số."
        )

        self.fields['password2'].help_text = (
            "Nhập lại mật khẩu giống phía trên để xác nhận."
        )
