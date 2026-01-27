from django import forms
from .models import BookedMovie
from django.forms import DateTimeInput

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

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
