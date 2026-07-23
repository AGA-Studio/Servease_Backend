from django.urls import path
from . import views

urlpatterns = [
    path('auth/', views.MeView.as_view(), name='usuario-me'),
    path('signup/', views.SignupView.as_view(), name='usuario-signup'),
    path('confirm-email/', views.ConfirmEmailView.as_view(), name='usuario-confirm-email'),
]
