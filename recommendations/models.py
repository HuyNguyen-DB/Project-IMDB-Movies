from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class UserProfile(models.Model):
    ROLE_NORMAL = "normal"
    ROLE_ROOM_STAFF = "room_staff"
    ROLE_BOOKING_STAFF = "booking_staff"

    ROLE_CHOICES = [
        (ROLE_NORMAL, "Người dùng thường"),
        (ROLE_ROOM_STAFF, "Nhân viên quản lý phòng chiếu"),
        (ROLE_BOOKING_STAFF, "Nhân viên vận hành đặt phim"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        primary_key=True,
        verbose_name="Người dùng"
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Số điện thoại"
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ngày sinh"
    )

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default=ROLE_NORMAL,
        verbose_name="Vai trò hệ thống"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tạo thông tin"
    )

    class Meta:
        verbose_name = "Thông tin người dùng"
        verbose_name_plural = "Thông tin người dùng"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Thông tin người dùng - {self.user.username}"


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

    poster_checked = models.BooleanField(
        default=False,
        verbose_name='Đã kiểm tra poster'
    )

    poster_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm cập nhật poster'
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
        ('booked', 'Đang được đặt'),
        ('maintenance', 'Bảo trì'),
        ('inactive', 'Ngưng sử dụng'),
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


class BookedMovie(models.Model):
    BOOKING_STATUS_CHOICES = [
        ('pending_payment', 'Chờ thanh toán'),
        ('confirmed', 'Đã xác nhận'),
        ('in_use', 'Đang sử dụng'),
        ('completed', 'Đã hoàn tất'),
        ('cancelled', 'Đã hủy'),
        ('expired', 'Hết hạn'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Chưa thanh toán'),
        ('paid', 'Đã thanh toán'),
        ('refund_pending', 'Đang chờ hoàn tiền'),
        ('refunded', 'Đã hoàn tiền'),
        ('failed', 'Thanh toán thất bại'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Người dùng'
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Phim'
    )

    booking_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        verbose_name='Mã đơn'
    )

    room = models.ForeignKey(
    ScreenRoom,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    verbose_name='Phòng chiếu'
    )

    rental_duration_minutes = models.IntegerField(
        verbose_name='Thời lượng thuê'
    )

    discount_amount = models.IntegerField(
        default=0,
        verbose_name='Số tiền giảm giá'
    )

    total_price = models.IntegerField(
        verbose_name='Tổng tiền sau giảm giá'
    )

    booking_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='Ngày giờ bắt đầu xem'
    )

    booking_end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Ngày giờ kết thúc xem'
    )

    date_booked = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Thời điểm tạo đơn'
    )

    booking_status = models.CharField(
        max_length=30,
        choices=BOOKING_STATUS_CHOICES,
        default='pending_payment',
        verbose_name='Trạng thái đơn'
    )

    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid',
        verbose_name='Trạng thái thanh toán'
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm thanh toán'
    )

    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời điểm hoàn tiền'
    )

    class Meta:
        verbose_name = 'Đơn đặt phim'
        verbose_name_plural = 'Đơn đặt phim'
        ordering = ['-booking_date', '-date_booked']

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = f"BM-{uuid.uuid4().hex[:10].upper()}"

        if self.booking_date and self.rental_duration_minutes:
            self.booking_end_time = (
                self.booking_date + timezone.timedelta(
                    minutes=self.rental_duration_minutes
                )
            )

        super().save(*args, **kwargs)

    def __str__(self):
        movie_name = self.movie.primaryTitle if self.movie else "Không rõ phim"
        return f"{self.booking_code} - {movie_name} - {self.user.username}"


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
        on_delete=models.PROTECT,
        related_name='invoice',
        verbose_name='Đơn đặt phim'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Người dùng'
    )

    customer_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Tên khách hàng'
    )

    customer_email = models.EmailField(
        blank=True,
        verbose_name='Email khách hàng'
    )

    movie_title = models.CharField(
        max_length=255,
        verbose_name='Tên phim tại thời điểm xuất hóa đơn'
    )

    room_name = models.CharField(
        max_length=255,
        verbose_name='Tên phòng tại thời điểm xuất hóa đơn'
    )

    booking_start_time = models.DateTimeField(
        verbose_name='Thời gian bắt đầu'
    )

    booking_end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Thời gian kết thúc'
    )

    rental_duration_minutes = models.IntegerField(
        verbose_name='Thời lượng thuê'
    )

    price_per_30min = models.IntegerField(
        verbose_name='Giá mỗi 30 phút'
    )

    discount_amount = models.IntegerField(
        default=0,
        verbose_name='Số tiền giảm'
    )

    final_amount = models.IntegerField(
        verbose_name='Thành tiền'
    )

    payment_status_at_issue = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Trạng thái thanh toán khi xuất hóa đơn'
    )

    issued_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Ngày xuất hóa đơn'
    )

    class Meta:
        verbose_name = 'Hóa đơn'
        verbose_name_plural = 'Hóa đơn'
        ordering = ['-issued_at']

    def save(self, *args, **kwargs):
        if not self.invoice_code:
            self.invoice_code = f"INV-{uuid.uuid4().hex[:10].upper()}"

        if self.booking:
            if not self.user_id:
                self.user = self.booking.user

            if not self.customer_name:
                full_name = (
                    f"{self.booking.user.first_name} {self.booking.user.last_name}"
                ).strip()
                self.customer_name = full_name or self.booking.user.username

            if not self.customer_email:
                self.customer_email = self.booking.user.email or ""

            if not self.movie_title:
                if self.booking.movie:
                    self.movie_title = self.booking.movie.primaryTitle
                else:
                    self.movie_title = "Không rõ phim"

            if not self.room_name:
                if self.booking.room:
                    self.room_name = self.booking.room.name
                else:
                    self.room_name = "Không rõ phòng"

            if not self.booking_start_time:
                self.booking_start_time = self.booking.booking_date

            if not self.booking_end_time:
                self.booking_end_time = self.booking.booking_end_time

            if not self.rental_duration_minutes:
                self.rental_duration_minutes = self.booking.rental_duration_minutes

            if not self.price_per_30min:
                if self.booking.room:
                    self.price_per_30min = self.booking.room.price_per_30min
                else:
                    self.price_per_30min = 0

            if self.discount_amount is None:
                self.discount_amount = self.booking.discount_amount

            if not self.final_amount:
                self.final_amount = self.booking.total_price

            if not self.payment_status_at_issue:
                self.payment_status_at_issue = self.booking.payment_status

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_code} - {self.customer_name}"


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