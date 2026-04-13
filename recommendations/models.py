from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class BookedMovie(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    movie_title = models.CharField(max_length=255)
    movie_genre = models.CharField(max_length=255)

    room_name = models.CharField(max_length=255)
    rental_duration_minutes = models.IntegerField()
    price_per_30min = models.IntegerField()
    total_price = models.IntegerField()

    booking_date = models.DateTimeField(default=timezone.now)
    date_booked = models.DateTimeField(auto_now_add=True)

    # NEW
    booking_code = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid'
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = f"BM-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_code} - {self.movie_title} - {self.user.username}"


class Invoice(models.Model):
    invoice_code = models.CharField(max_length=50, unique=True, blank=True)
    booking = models.OneToOneField(
        BookedMovie,
        on_delete=models.CASCADE,
        related_name='invoice'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_code:
            self.invoice_code = f"INV-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_code} - {self.user.username}"


class Movie(models.Model):
    tconst = models.CharField(max_length=20, primary_key=True)
    primaryTitle = models.CharField(max_length=255)
    startYear = models.IntegerField()
    runtimeMinutes = models.IntegerField(null=True, blank=True)
    genres = models.CharField(max_length=255)
    averageRating = models.FloatField(null=True, blank=True)
    numVotes = models.IntegerField(null=True, blank=True)
    poster_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.primaryTitle


class ScreenRoom(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('maintenance', 'Maintenance'),
        ('booked', 'Booked'),
    ]

    room_id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    image = models.ImageField(
        upload_to='screen_rooms/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    price_per_30min = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.room_id} - {self.name}"


class RoomImage(models.Model):
    room = models.ForeignKey(
        ScreenRoom,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='screen_rooms/gallery/')

    def __str__(self):
        return f"{self.room.name} - {self.image.name}"