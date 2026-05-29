from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),

    path('recommend/', views.recommend_page, name='recommend'),

    path('choose-genres/', views.choose_genres, name='choose_genres'),

    path(
        'login/',
        views.CustomLoginView.as_view(
            template_name='recommendations/login.html'
        ),
        name='login'
    ),

    path('logout/', views.custom_logout, name='logout'),

    path('signup/', views.signup, name='signup'),

    path('user_home/', views.user_home, name='user_home'),

    # Thông tin cá nhân
    path('profile/', views.profile_detail, name='profile_detail'),

    path('profile/edit/', views.edit_profile, name='edit_profile'),

    path(
        'profile/password/',
        auth_views.PasswordChangeView.as_view(
            template_name='recommendations/password_change.html',
            success_url='/profile/password/done/'
        ),
        name='password_change'
    ),

    path(
        'profile/password/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='recommendations/password_change_done.html'
        ),
        name='password_change_done'
    ),

    path('book_movie/', views.book_movie, name='book_movie'),

    path('room/<str:room_id>/', views.room_detail, name='room_detail'),

    path('movies/', views.movie_list, name='movie_list'),

    path('handle-booking/', views.handle_booking, name='handle_booking'),

    path(
        'handle-booking/<str:room_id>/',
        views.handle_booking,
        name='handle_booking_with_room'
    ),

    path(
        'select-movie/<str:movie_id>/',
        views.select_movie,
        name='select_movie'
    ),

    path('rooms/', views.room_list, name='room_list'),

    path(
        'payment/<int:booking_id>/',
        views.payment_page,
        name='payment_page'
    ),

    path(
        'payment/<int:booking_id>/confirm/',
        views.confirm_payment,
        name='confirm_payment'
    ),

    path(
        'invoice/<str:invoice_code>/',
        views.invoice_detail,
        name='invoice_detail'
    ),
    path("webhook/sepay/", views.sepay_webhook, name="sepay_webhook"),

    path("chatbot/", views.chatbot_api, name="chatbot_api"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)