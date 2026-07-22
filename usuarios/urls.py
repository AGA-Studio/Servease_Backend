from django.urls import path
from . import views

urlpatterns = [
    path('auth/', views.me, name='usuario-me'),
    path('signup/', views.SignupView.as_view(), name='usuario-signup'),
]
