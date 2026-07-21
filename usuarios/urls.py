from django.urls import path
from . import views

urlpatterns = [
    path('auth/', views.me, name='usuario-me'),
]
