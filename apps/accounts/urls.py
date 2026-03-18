"""URL patterns for patient authentication."""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('start/', views.start_view, name='start'),
    path('token-expired/', views.token_expired_view, name='token_expired'),
    path('verify-dob/', views.verify_dob_view, name='verify_dob'),
    path('resend-link/', views.resend_link_view, name='resend_link'),
    path('manual-entry/', views.manual_entry_view, name='manual_entry'),
    path('logout/', views.logout_view, name='logout'),
]
