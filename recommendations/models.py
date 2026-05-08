from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Người dùng'
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Số điện thoại'
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name='Ngày sinh'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày tạo thông tin'
    )

    class Meta:
        verbose_name = 'Thông tin người dùng'
        verbose_name_plural = 'Thông tin người dùng'
        ordering = ['-created_at']

    def __str__(self):
        return f"Thông tin người dùng - {self.user.username}"


class BookedMovie(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Chờ thanh toán'),
        ('confirmed', 'Đã xác nhận'),
        ('cancelled', 'Đã hủy'),
        ('expired', 'Hết hạn'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Chưa thanh toán'),
        ('paid', 'Đã thanh toán'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Người dùng'
    )

    movie_title = models.CharField(
        max_length=255,
        verbose_name='Tên phim'
    )

    movie_genre = models.CharField(
        max_length=255,
        verbose_name='Thể loại phim'
    )

    room_name = models.CharField(
        max_length=255,
        verbose_name='Tên phòng chiếu'
    )

    rental_duration_minutes = models.IntegerField(
        verbose_name='Thời lượng thuê'
    )

    price_per_30min = models.IntegerField(
        verbose_name='Giá mỗi 30 phút'
    )

    total_price = models.IntegerField(
        verbose_name='Tổng tiền'
    )

    booking_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='Ngày giờ xem'
    )

    date_booked = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Thời điểm tạo đơn'
    )

    booking_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        verbose_name='Mã đơn'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Trạng thái đơn'
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid',
        verbose_name='Trạng thái thanh toán'
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm thanh toán'
    )

    class Meta:
        verbose_name = 'Đơn đặt phim'
        verbose_name_plural = 'Đơn đặt phim'
        ordering = ['-booking_date', '-date_booked']

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = f"BM-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_code} - {self.movie_title} - {self.user.username}"


class Invoice(models.Model):
    invoice_code = models.CharField(
        max_length=50,
        primary_key=True,
        unique=True,
        blank=True,
        verbose_name='Mã hóa đơn'
    )

    booking = models.OneToOneField(
        BookedMovie,
        on_delete=models.CASCADE,
        related_name='invoice',
        verbose_name='Đơn đặt phim'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Người dùng'
    )

    amount = models.IntegerField(
        verbose_name='Số tiền'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày tạo hóa đơn'
    )

    class Meta:
        verbose_name = 'Hóa đơn'
        verbose_name_plural = 'Hóa đơn'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_code:
            self.invoice_code = f"INV-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_code} - {self.user.username}"


class Movie(models.Model):
    tconst = models.CharField(
        max_length=20,
        primary_key=True,
        verbose_name='Mã phim'
    )

    primaryTitle = models.CharField(
        max_length=255,
        verbose_name='Tên phim'
    )

    startYear = models.IntegerField(
        verbose_name='Năm phát hành'
    )

    runtimeMinutes = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Thời lượng phim'
    )

    genres = models.CharField(
        max_length=255,
        verbose_name='Thể loại'
    )

    averageRating = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Điểm đánh giá'
    )

    numVotes = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Số lượt đánh giá'
    )

    poster_url = models.URLField(
        null=True,
        blank=True,
        verbose_name='Đường dẫn poster'
    )

    class Meta:
        verbose_name = 'Phim'
        verbose_name_plural = 'Phim'
        ordering = ['-startYear', '-averageRating', 'primaryTitle']

    def __str__(self):
        return self.primaryTitle


class ScreenRoom(models.Model):
    STATUS_CHOICES = [
        ('available', 'Sẵn sàng'),
        ('maintenance', 'Bảo trì'),
        ('booked', 'Đã đặt'),
    ]

    room_id = models.CharField(
        max_length=20,
        primary_key=True,
        verbose_name='Mã phòng'
    )

    name = models.CharField(
        max_length=100,
        verbose_name='Tên phòng'
    )

    description = models.TextField(
        blank=True,
        verbose_name='Mô tả'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        verbose_name='Trạng thái phòng'
    )

    image = models.ImageField(
        upload_to='screen_rooms/',
        null=True,
        blank=True,
        verbose_name='Ảnh chính'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày tạo'
    )

    price_per_30min = models.IntegerField(
        default=0,
        verbose_name='Giá mỗi 30 phút'
    )

    class Meta:
        verbose_name = 'Phòng chiếu'
        verbose_name_plural = 'Phòng chiếu'
        ordering = ['room_id']

    def __str__(self):
        return f"{self.room_id} - {self.name}"


class RoomImage(models.Model):
    room = models.ForeignKey(
        ScreenRoom,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Phòng chiếu'
    )

    image = models.ImageField(
        upload_to='screen_rooms/gallery/',
        verbose_name='Ảnh phụ'
    )

    class Meta:
        verbose_name = 'Ảnh phụ phòng chiếu'
        verbose_name_plural = 'Ảnh phụ phòng chiếu'
        ordering = ['id']

    def __str__(self):
        return f"{self.room.name} - {self.image.name}"