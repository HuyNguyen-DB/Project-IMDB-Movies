from django.contrib.auth.signals import user_logged_in
from django.shortcuts import redirect
from django.dispatch import receiver
from django.urls import reverse

@receiver(user_logged_in)
def redirect_user_based_on_role(sender, request, user, **kwargs):
    if user.is_staff:  # Kiểm tra xem người dùng có phải là admin không
        return redirect(reverse('admin:index'))  # Nếu là admin, chuyển hướng đến trang admin
    else:
        return redirect(reverse('home'))  # Nếu là user, chuyển hướng đến trang chủ hoặc trang dành cho user
