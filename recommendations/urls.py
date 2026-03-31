from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # Import views để kết nối với các hàm xử lý
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Trang chủ của ứng dụng
    path('', views.home, name='home'),  
    
    # Trang gợi ý phim
    path('recommend/', views.recommend_page, name='recommend'),  
    
    # TRANG CHỌN THỂ LOẠI
    path('choose-genres/', views.choose_genres, name='choose_genres'),
    
    # Đăng nhập và đăng xuất (Sử dụng CustomLoginView và custom_logout nếu cần)
    path('login/', views.CustomLoginView.as_view(template_name='recommendations/login.html'), name='login'),  # Đảm bảo sử dụng CustomLoginView
    path('logout/', views.custom_logout, name='logout'),  # Dùng custom_logout để xử lý đăng xuất
    
    # Đăng ký
    path('signup/', views.signup, name='signup'),
    
    # Trang dành cho user đã đăng nhập
    path('user_home/', views.user_home, name='user_home'),
    
    # Đặt phim
    path('book_movie/', views.book_movie, name='book_movie'),

    path('room/<str:room_id>/', views.room_detail, name='room_detail'),

    path('movies/', views.movie_list, name='movie_list'),

    path('handle-booking/', views.handle_booking, name='handle_booking'),
    path('handle-booking/<str:room_id>/', views.handle_booking, name='handle_booking_with_room'),

    path('select-movie/<str:movie_id>/', views.select_movie, name='select_movie'),
    path('rooms/', views.room_list, name='room_list'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
