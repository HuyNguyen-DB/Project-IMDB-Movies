# admin.py
from django.contrib import admin
from .models import BookedMovie, Movie

# Tạo một class để quản lý cách hiển thị BookedMovie trong Admin
class BookedMovieAdmin(admin.ModelAdmin):
    # Định nghĩa các trường cần hiển thị trong danh sách
    list_display = ('user', 'movie_title', 'movie_genre', 'booking_date', 'date_booked')
    
    # Các bộ lọc để lọc theo các trường như user, movie_genre
    list_filter = ('user', 'movie_genre', 'booking_date')

    # Các trường có thể tìm kiếm trong Admin
    search_fields = ('user__username', 'movie_title', 'movie_genre')

    # Định nghĩa cách hiển thị chi tiết khi bấm vào 1 đối tượng
    def movie_title_genre(self, obj):
        return f"{obj.movie_title} - {obj.movie_genre}"
    movie_title_genre.short_description = 'Movie (Title - Genre)'

# Đăng ký model BookedMovie vào Admin
admin.site.register(BookedMovie, BookedMovieAdmin)

# Đăng ký model Movie vào Admin nếu cần
class MovieAdmin(admin.ModelAdmin):
    list_display = ('primaryTitle', 'startYear', 'runtimeMinutes', 'genres', 'averageRating')
    search_fields = ('primaryTitle', 'genres')

admin.site.register(Movie, MovieAdmin)
