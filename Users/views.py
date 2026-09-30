import logging
from tokenize import TokenError

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.cache import cache  
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.hashers import make_password
from django_ratelimit.decorators import ratelimit

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView

from axes.handlers.proxy import AxesProxyHandler

from Users.authentication import CustomJWTAuthentication 
from Users.serializers import UserRegistrationSerializer, LoginSerializer
from Users.permissions import IsAdminUserRole
from Users.validators import CustomPasswordValidator
from Users.models import Users 

from notification.helpers import notify_user

from .utils import *

logger = logging.getLogger('users')

def register_page(request):
    return render(request, "register.html")

def login_page(request):
    return render(request, "login.html")

@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
class UserRegistration(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [CustomJWTAuthentication, SessionAuthentication]

    def post(self, request):
        try:
            logger.info("[UserRegistration POST] API called")

            ip = get_client_ip(request)
            logger.info(f"[UserRegistration POST] Client IP: {ip}")

            allowed = check_ip_limit("register_ip_limit", ip, 10, IP_EXPIRY)

            if not allowed:
                logger.warning(f"[UserRegistration POST] IP limit exceeded: {ip}")
                return JsonResponse({"error": "Too many requests"}, status=429)

            data = request.data.copy()
            email = data.get("user_email")
            role = data.get("role")

            logger.info(f"[UserRegistration POST] Registration attempt for email: {email} with role: {role}")

            custom_validator = CustomPasswordValidator()

            try:
                custom_validator.validate(data.get("password"))
            except ValidationError as e:
                logger.warning(f"[UserRegistration POST] Invalid password for email: {email}")
                return JsonResponse({"error": str(e)}, status=400)

            if data.get("password") != data.get("confirm_password"):
                logger.warning(f"[UserRegistration POST] Password mismatch for email: {email}")
                return JsonResponse({"error": "Password mismatch"}, status=400)

            allowed_roles = ["jobseeker", "recruiter", "admin"]
            if role not in allowed_roles:
                logger.warning(f"[UserRegistration POST] Invalid role '{role}' for email: {email}")
                return JsonResponse({"error": "Invalid role"}, status=400)

            if role == "admin":
                is_admin = (
                    request.user 
                    and request.user.is_authenticated 
                    and (getattr(request.user, "role", None) == "admin" or request.user.is_staff or request.user.is_superuser)
                )
                if not is_admin:
                    logger.warning(f"[UserRegistration POST] Unauthorized admin registration attempt by user: {request.user}")
                    return JsonResponse({
                        "error": "Unauthorized: Only an authenticated administrator can register a new admin."
                    }, status=403)

            user = Users.objects.filter(user_email=email).first()
            if user:
                logger.warning(f"[UserRegistration POST] User already exists: {email}")
                if user.is_active:
                    logger.warning(f"[UserRegistration POST] Active account already exists: {email}")
                    return JsonResponse({"error": "Email already registered"}, status=400)

                logger.warning(f"[UserRegistration POST] Deleted account tried to re-register: {email}")
                return JsonResponse({"error": "Account deleted. Use a new email."}, status=400)

            raw_password = data.get("password")
            logger.info(f"[UserRegistration POST] Hashing password for email: {email}")
            
            hashed_password = make_password(raw_password)
            data["password"] = hashed_password
            data.pop("confirm_password", None)

            logger.info(f"[UserRegistration POST] Generating OTP for email: {email}")
            otp = generate_otp(email, request)
            if not otp:
                logger.warning(f"[UserRegistration POST] OTP request limit exceeded for email: {email}")
                return JsonResponse({"error": "Too many OTP requests. Try again later."}, status=429)

            verify_token = create_verify_token(email)
            logger.info(f"[UserRegistration POST] Verification token created for email: {email}")

            cache.set(f"register:{email}", data, timeout=SESSION_EXPIRY)
            logger.info(f"[UserRegistration POST] Registration data cached for email: {email}")

            send_otp_email_task.delay(email, otp)
            logger.info(f"[UserRegistration POST] OTP email task queued successfully for email: {email}")

            return JsonResponse({
                "message": "OTP sent to email",
                "verify_token": verify_token
            }, status=200)

        except Exception as e:
            logger.exception(f"[UserRegistration POST] Error in UserRegistration: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(ratelimit(key='ip', rate='10/m', block=True), name='post')
class VerifyEmailOTP(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  

    def post(self, request):
        try:
            logger.info("[VerifyEmailOTP POST] API called")

            otp = request.data.get("otp")
            token = request.data.get("verify_token")

            if not otp or not token:
                logger.warning("[VerifyEmailOTP POST] OTP or token missing")
                return JsonResponse({"error": "OTP and token required"}, status=400)

            ip = get_client_ip(request)
            
            valid_attempt = check_token_attempt(token, ip)
            if not valid_attempt:
                logger.warning(f"[VerifyEmailOTP POST] Too many token attempts from IP: {ip}")
                return JsonResponse({"error": "Too many attempts"}, status=429)

            email = get_email_from_token(token)
            if not email:
                logger.warning("[VerifyEmailOTP POST] Invalid or expired verification token")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            otp_attempt = check_otp_attempt(email)
            if not otp_attempt:
                logger.warning(f"[VerifyEmailOTP POST] Too many OTP attempts for email: {email}")
                return JsonResponse({"error": "Too many wrong attempts"}, status=429)

            valid, msg = verify_otp(email, otp)
            if not valid:
                logger.warning(f"[VerifyEmailOTP POST] Invalid OTP entered for email: {email}")
                return JsonResponse({"error": msg}, status=400)

            logger.info(f"[VerifyEmailOTP POST] OTP verified successfully for email: {email}")

            user_data = cache.get(f"register:{email}")
            if not user_data:
                logger.warning(f"[VerifyEmailOTP POST] Registration session expired for email: {email}")
                return JsonResponse({"error": "Session expired"}, status=400)

            serializer = UserRegistrationSerializer(data=user_data)
            if not serializer.is_valid():
                logger.error(f"[VerifyEmailOTP POST] Serializer validation failed for email: {email} | Errors: {serializer.errors}")
                return JsonResponse(serializer.errors, status=400)

            logger.info(f"[VerifyEmailOTP POST] Serializer validated successfully for email: {email}")
            
            save_kwargs = {"is_verified": True}
            if user_data.get("role") == "admin":
                save_kwargs["is_staff"] = True

            serializer.save(**save_kwargs)
            logger.info(f"[VerifyEmailOTP POST] User account created successfully for email: {email}")

            user = Users.objects.get(user_email=email)

            logger.info(f"[VerifyEmailOTP POST] Sending welcome notification to user: {email}")
            notify_user(
                recipient=user,
                title="Welcome to Job Portal",
                message="Your account was created successfully",
                notification_type="system",
                send_email=True
            )

            clear_verification_cache(email, token, ip)
            cache.delete(f"register:{email}")
            logger.info(f"[VerifyEmailOTP POST] Caches cleared. Registration complete for email: {email}")

            return JsonResponse({"message": "Registration successful"}, status=200)

        except Exception as e:
            logger.exception(f"[VerifyEmailOTP POST] Error in VerifyEmailOTP: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class ResendOTP(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            logger.info("[ResendOTP POST] API called")

            token = request.data.get("verify_token")
            if not token:
                logger.warning("[ResendOTP POST] Verify token missing")
                return JsonResponse({"error": "Token required"}, status=400)

            email = get_email_from_token(token)
            if not email:
                logger.warning("[ResendOTP POST] Invalid or expired token")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)

            logger.info(f"[ResendOTP POST] Resending OTP for email: {email}")

            cache.delete(f"otp_attempt:{email}")

            otp = generate_otp(email, request)
            if not otp:
                logger.warning(f"[ResendOTP POST] OTP resend limit exceeded for email: {email}")
                return JsonResponse({"error": "Too many requests. Try later."}, status=429)

            send_otp_email_task.delay(email, otp)
            logger.info(f"[ResendOTP POST] OTP resend email task queued successfully for email: {email}")

            return JsonResponse({"message": "OTP resent successfully"}, status=200)

        except Exception as e:
            logger.exception(f"[ResendOTP POST] Error in ResendOTP: {str(e)}")
            return JsonResponse({"error": "Internal server error"}, status=500)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        if AxesProxyHandler.is_locked(request):
            logger.error(f"Access denied: Account is currently locked for IP:{get_client_ip(request)} - {request.data.get('email')}")
            return Response({
                "detail": "Account locked due to too many failed attempts. Please wait 15 minutes."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            serializer = LoginSerializer(data=request.data, context={"request": request})
            
            if not serializer.is_valid():
                logger.warning(f"Login failed: Invalid credentials for {request.data.get('email')}")
                return Response(
                    {"detail": "Invalid email or password."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = serializer.validated_data["user"]
            refresh = RefreshToken.for_user(user)
            
            logger.info(f"User logged in: {user.user_email} - IP: {get_client_ip(request)}")
            
            response = Response({
                "access": str(refresh.access_token),
                "user": {
                    "user_id": user.user_id,
                    "user_email": user.user_email,
                    "role": getattr(user, 'role', 'jobseeker'),
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser
                }
            }, status=status.HTTP_200_OK)
            
            response.set_cookie(
                key='refresh_token',
                value=str(refresh),
                httponly=True,
                secure=True,
                samesite='Lax',
                max_age=7 * 24 * 60 * 60
            )
            return response

        except PermissionDenied:
            return Response({
                "detail": "Too many attempts. Your account is now locked for 15 minutes."
            }, status=status.HTTP_403_FORBIDDEN)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if not refresh_token:
                return Response({"detail": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()
            
            logger.info(f"User logged out: {request.user.user_email}")
            
            response = Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)
            response.delete_cookie('refresh_token')
            return response
            
        except TokenError as e:
            logger.warning(f"Logout failed: Invalid token - {str(e)}")
            return Response({"detail": "Token is invalid or expired"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({"detail": "Internal server error"}, status=500)


class DashboardView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return render(request, "home.html")


class UserDetailsView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        role = getattr(user, 'role', None)
        if user.is_staff or user.is_superuser or role == 'admin':
            role = 'admin'
        elif not role:
            role = 'jobseeker'

        return Response({
            "user_id": user.user_id if hasattr(user, 'user_id') else user.pk,
            "user_email": user.user_email if hasattr(user, 'user_email') else user.email,
            "role": role,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser
        })
    
@method_decorator(ratelimit(key='user', rate='3/m', block=True), name='post')
class AdminPasswordChangeRequestView(APIView):
    """
    Step 1: Admin verifies old password and provides new password.
    An OTP is sent to the admin's email and new password hash is temporarily cached.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        try:

            token = request.data.get("verify_token")

            email = get_email_from_token(token)
            if not email:
                logger.warning("[VerifyEmailOTP POST] Invalid or expired verification token")
                return JsonResponse({"error": "Invalid or expired token"}, status=400)
            
            data = request.data.copy()

            current_password = data.get("current_password")
            new_password = data.get("new_password")
            confirm_password = data.get("confirm_password")

            if not current_password or not new_password or not confirm_password:
                return Response(
                    {"error": "Current password, new password, and confirmation are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            custom_validator = CustomPasswordValidator()
            
            try:
                custom_validator.validate(data.get("new_password"))
            except ValidationError as e:
                logger.warning(f"[UserRegistration POST] Invalid password for email: {email}")
                return JsonResponse({"error": str(e)}, status=400)
            
            # Validate new password strength and matching
            if new_password != confirm_password:
                return Response({"error": "New passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

            if current_password == new_password:
                return Response({"error": "New password cannot be identical to the current password."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate OTP
            otp = generate_otp(email, request)
            if not otp:
                logger.warning(f"[AdminPasswordChangeRequest] OTP request limit exceeded for: {email}")
                return Response({"error": "Too many OTP requests. Please try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

            verify_token = create_verify_token(email)

            # Cache the hashed new password under an isolated prefix
            cache_payload = {
                "new_password_hash": make_password(new_password)
            }
            cache.set(f"pwd_change:{email}", cache_payload, timeout=SESSION_EXPIRY)

            # Queue OTP email
            send_otp_email_task.delay(email, otp)
            logger.info(f"[AdminPasswordChangeRequest] OTP sent for password update to: {email}")

            return Response({
                "message": "OTP has been sent to your email.",
                "verify_token": verify_token
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[AdminPasswordChangeRequest] Error: {str(e)}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(ratelimit(key='ip', rate='10/m', block=True), name='post')
class AdminPasswordChangeConfirmView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        try:
            
            otp = request.data.get("otp")
            token = request.data.get("verify_token")

            if not otp or not token:
                return Response({"error": "OTP and verify token are required."}, status=status.HTTP_400_BAD_REQUEST)

            ip = get_client_ip(request)

            if not check_token_attempt(token, ip):
                return Response({"error": "Too many attempts. Please try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

            email = get_email_from_token(token)

            if not check_otp_attempt(email):
                return Response({"error": "Too many wrong attempts. Please request a new OTP."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

            valid, msg = verify_otp(email, otp)
            if not valid:
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

            cached_data = cache.get(f"pwd_change:{email}")
            if not cached_data or "new_password_hash" not in cached_data:
                return Response({"error": "Password change session expired. Please start over."}, status=status.HTTP_400_BAD_REQUEST)

            admin_user = Users.objects.filter(user_email=email).first()

            if not admin_user:
                return Response({"error": "Admin user not found."}, status=status.HTTP_404_NOT_FOUND)

            admin_user.password = cached_data["new_password_hash"]
            admin_user.save()

            clear_verification_cache(email, token, ip)
            cache.delete(f"pwd_change:{email}")
            logger.info(f"[AdminPasswordChangeConfirm] Password successfully changed for admin: {email}")

            return Response({
                "message": "Password changed successfully."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[AdminPasswordChangeConfirm] Error: {str(e)}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)