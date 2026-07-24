from django.urls import path
from . import views

urlpatterns = [
    path('auth/', views.MeView.as_view(), name='usuario-me'),
    path('auth/personal-info/', views.UpdatePersonalInfoView.as_view(), name='usuario-personal-info'),
    path('signup/', views.SignupView.as_view(), name='usuario-signup'),
    path('confirm-email/', views.ConfirmEmailView.as_view(), name='usuario-confirm-email'),
    path('settings/password-reset/', views.RequestPasswordResetView.as_view(), name='usuario-password-reset'),
    path('mfa/enroll/', views.MfaEnrollView.as_view(), name='usuario-mfa-enroll'),
    path('mfa/<str:factor_id>/challenge/', views.MfaChallengeView.as_view(), name='usuario-mfa-challenge'),
    path('mfa/<str:factor_id>/verify/', views.MfaVerifyView.as_view(), name='usuario-mfa-verify'),
    path('<uuid:id_usuario>/disable/', views.DisableUserView.as_view(), name='usuario-disable'),
    path('<uuid:id_usuario>/perfil-cliente/', views.PerfilClienteView.as_view(), name='usuario-perfil-cliente'),
    path('<uuid:id_usuario>/reviews/', views.ReviewsClienteView.as_view(), name='usuario-reviews'),
    path('<uuid:id_usuario>/ultimas-publicaciones/', views.UltimasPublicacionesClienteView.as_view(), name='usuario-ultimas-publicaciones'),
    path('<uuid:id_usuario>/home/', views.HomeClienteView.as_view(), name='usuario-home-cliente'),
]