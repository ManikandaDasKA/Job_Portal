from django.urls import path
from Users import views

urlpatterns = [
    path('register-test/', views.UserRegistration.as_view(), name='register_test'),
    path('verify-email-otp-test/', views.VerifyEmailOTP.as_view(), name='verify_email_otp_test'),
    path('resend-otp-test/', views.ResendOTP.as_view(), name='resend_otp_test'),
    path('registration/', views.register_page, name='registration'),
    path('Admin-Password-Change-Request/', views.AdminPasswordChangeRequestView.as_view(), name='admin_password_change_request'),
    path('Admin-Password-Change-Confirm/', views.AdminPasswordChangeConfirmView.as_view(), name='admin_password_change_confirm'),

    # Login & Refresh
    path('login-test/', views.LoginView.as_view(), name='login_test'),
    path('logout-test/', views.LogoutView.as_view(), name='logout_test'),

     # 2. This is the API endpoint your JavaScript calls
    path('login/', views.login_page, name='login'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('details/', views.UserDetailsView.as_view(), name='details'),
]
