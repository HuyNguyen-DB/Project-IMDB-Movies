from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class BookedMovie(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie_title = models.CharField(max_length=255)
    movie_genre = models.CharField(max_length=255)
    date_booked = models.DateTimeField(auto_now_add=True)
    booking_date = models.DateTimeField(default=timezone.now)  # Thêm trường này để lưu ngày và giờ đặt phim

    def __str__(self):
        return f"{self.movie_title} - {self.movie_genre} - {self.booking_date}"
class Movie(models.Model):
    # Mã định danh phim, khóa chính, với độ dài tối đa là 20 ký tự
    tconst = models.CharField(max_length=20, primary_key=True)
    
    # Tiêu đề chính của phim, với độ dài tối đa là 255 ký tự
    primaryTitle = models.CharField(max_length=255)
    
    # Năm phát hành phim (start year)
    startYear = models.IntegerField()
    
    # Thời gian chạy của phim, có thể null nếu không có dữ liệu
    runtimeMinutes = models.IntegerField(null=True, blank=True)
    
    # Thể loại của phim, có thể là một chuỗi dài các thể loại phân cách bằng dấu phẩy
    genres = models.CharField(max_length=255)

    # Đánh giá trung bình của phim, có thể null nếu không có dữ liệu
    averageRating = models.FloatField(null=True, blank=True)

    # Số lượng bình chọn của phim, có thể null nếu không có dữ liệu
    numVotes = models.IntegerField(null=True, blank=True)

    poster_url = models.URLField(null=True, blank=True)
    def __str__(self):
        # Trả về tiêu đề chính của phim khi in đối tượng Movie
        return self.primaryTitle
    

   
class ScreenRoom(models.Model):

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('maintenance', 'Maintenance'),
        ('booked', 'Booked'),
    ]
    room_id = models.CharField(
        max_length=20,
        primary_key=True
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    # Thuộc tính hình ảnh
    image = models.ImageField(
        upload_to='screen_rooms/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.room_id} - {self.name}"
    

class RoomImage(models.Model):
    room = models.ForeignKey(
        ScreenRoom,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image = models.ImageField(
        upload_to='screen_rooms/gallery/'
    )

    def __str__(self):
        return f"{self.room.name} - {self.image.name}"