# admin.py
from django.contrib import admin
from .models import BookedMovie, Movie,  ScreenRoom, RoomImage
from django.utils.html import format_html

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



@admin.register(ScreenRoom)
class ScreenRoomAdmin(admin.ModelAdmin):

    list_display = (
        'room_id',
        'name',
        'colored_status',
        'image_preview',
        'created_at',
    )

    search_fields = ('room_id', 'name')
    list_filter = ('status', 'created_at')
    ordering = ('room_id',)

    readonly_fields = ('created_at', 'image_preview')

    fieldsets = (
        ('Thông tin phòng', {
            'fields': ('room_id', 'name', 'description', 'status')
        }),
        ('Hình ảnh', {
            'fields': ('image', 'image_preview')
        }),
        ('Thời gian', {
            'fields': ('created_at',)
        }),
    )

    # Hiển thị ảnh thumbnail trong list và detail
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" style="border-radius:6px;" />',
                obj.image.url
            )
        return "No Image"

    image_preview.short_description = "Preview"

    # Tô màu trạng thái cho trực quan
    def colored_status(self, obj):
        color_map = {
            'available': 'green',
            'maintenance': 'orange',
            'booked': 'red'
        }
        color = color_map.get(obj.status, 'black')
        return format_html(
            '<strong style="color:{};">{}</strong>',
            color,
            obj.get_status_display()
        )

    colored_status.short_description = "Status"

@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ('room', 'image')
    list_filter = ('room',)
