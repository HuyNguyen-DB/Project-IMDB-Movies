# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import BookedMovie, Movie, ScreenRoom, RoomImage


class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1
    fields = ('image',)


@admin.register(BookedMovie)
class BookedMovieAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'movie_title',
        'movie_genre',
        'room_name',
        'rental_duration_minutes',
        'price_per_30min',
        'formatted_total_price',
        'booking_date',
        'date_booked',
    )

    list_filter = (
        'user',
        'movie_genre',
        'booking_date',
        'date_booked',
    )

    search_fields = (
        'user__username',
        'movie_title',
        'movie_genre',
        'room_name',
    )

    ordering = ('-date_booked',)

    readonly_fields = (
        'user',
        'movie_title',
        'movie_genre',
        'room_name',
        'rental_duration_minutes',
        'price_per_30min',
        'total_price',
        'date_booked',
    )

    fieldsets = (
        ('Thông tin người đặt', {
            'fields': ('user',)
        }),
        ('Thông tin phim', {
            'fields': ('movie_title', 'movie_genre')
        }),
        ('Thông tin phòng', {
            'fields': ('room_name',)
        }),
        ('Thông tin thuê phòng', {
            'fields': (
                'rental_duration_minutes',
                'price_per_30min',
                'total_price',
                'booking_date',
                'date_booked',
            )
        }),
    )

    def formatted_total_price(self, obj):
        if obj.total_price is None:
            return "Chưa có giá"
        return f"{obj.total_price:,} VND"


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = (
        'primaryTitle',
        'startYear',
        'runtimeMinutes',
        'genres',
        'averageRating',
    )
    search_fields = ('primaryTitle', 'genres', 'tconst')
    list_filter = ('startYear',)
    ordering = ('-startYear',)


@admin.register(ScreenRoom)
class ScreenRoomAdmin(admin.ModelAdmin):
    list_display = (
        'room_id',
        'name',
        'room_type_display',
        'formatted_price_per_30min',
        'colored_status',
        'image_preview',
        'created_at',
    )

    search_fields = ('room_id', 'name', 'description')
    list_filter = ('status', 'created_at')
    ordering = ('room_id',)

    readonly_fields = ('created_at', 'image_preview')

    inlines = [RoomImageInline]

    actions = (
        'set_price_normal',
        'set_price_vip',
        'set_price_group',
    )

    fieldsets = (
        ('Thông tin phòng', {
            'fields': ('room_id', 'name', 'description', 'status')
        }),
        ('Giá thuê', {
            'fields': ('price_per_30min',)
        }),
        ('Hình ảnh', {
            'fields': ('image', 'image_preview')
        }),
        ('Thời gian', {
            'fields': ('created_at',)
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" style="border-radius:6px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = "Preview"

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

    def room_type_display(self, obj):
        name = (obj.name or '').lower()
        if 'vip' in name:
            return 'VIP'
        if 'nhóm' in name or 'group' in name:
            return 'Nhóm'
        if 'thường' in name or 'normal' in name:
            return 'Thường'
        return 'Khác'
    room_type_display.short_description = "Loại phòng"

    def formatted_price_per_30min(self, obj):
        if obj.price_per_30min is None:
            return "Chưa có giá"
        return f"{obj.price_per_30min:,} VND"

    def set_price_normal(self, request, queryset):
        updated = queryset.update(price_per_30min=40000)
        self.message_user(request, f'Đã cập nhật {updated} phòng thành 40,000 VND / 30 phút.')
    set_price_normal.short_description = 'Đặt giá phòng thường = 40,000 / 30 phút'

    def set_price_vip(self, request, queryset):
        updated = queryset.update(price_per_30min=60000)
        self.message_user(request, f'Đã cập nhật {updated} phòng thành 60,000 VND / 30 phút.')
    set_price_vip.short_description = 'Đặt giá phòng VIP = 60,000 / 30 phút'

    def set_price_group(self, request, queryset):
        updated = queryset.update(price_per_30min=90000)
        self.message_user(request, f'Đã cập nhật {updated} phòng thành 90,000 VND / 30 phút.')
    set_price_group.short_description = 'Đặt giá phòng nhóm = 90,000 / 30 phút'


@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ('room', 'image')
    list_filter = ('room',)
    search_fields = ('room__room_id', 'room__name')