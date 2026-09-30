from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, APIException, PermissionDenied
from rest_framework.throttling import UserRateThrottle

from django.shortcuts import render
from django.db import IntegrityError
from django.core.exceptions import ObjectDoesNotExist


from notification.helpers import notify_user

from .serializers import CompanySerializer, RecruiterSerializer
from .models import Company, Recruiter
from .permission import HasCompanyAccess

import logging

logger = logging.getLogger(__name__)


class BurstRateThrottle(UserRateThrottle):
    """Prevents high-frequency API flooding (e.g., script attacks)."""
    scope = 'burst'
    rate = '60/minute'


class SustainedRateThrottle(UserRateThrottle):
    """Prevents continuous background scraping and resource draining."""
    scope = 'sustained'
    rate = '1000/day'


def CompanyProfileTemplate(request):
    return render(request, 'add_company.html')


def RecruiterProfileTemplate(request):
    return render(request, 'recruiter_profile.html')


def admin_page(request):
    return render(request, "admin.html")


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get_queryset(self):
        try:
            user = self.request.user

            # Superusers can see every company
            if user.is_superuser:
                return Company.objects.all().order_by('-created_at')

            # Any recruiter linked to a company can VIEW it (read-only methods).
            # Write methods still require an approved recruiter (have_access=True).
            filters = {'recruiters__user': user}
            if self.request.method not in SAFE_METHODS:
                filters['recruiters__have_access'] = True

            queryset = Company.objects.filter(**filters).distinct().order_by('-created_at')
            logger.info(f"Company details fetched by user {user.user_id}")
            return queryset

        except Exception as e:
            logger.error(
                f"Error fetching company queryset for user {getattr(self.request.user, 'user_id', 'Unknown')}: {str(e)}",
                exc_info=True
            )
            raise APIException("An unexpected error occurred while retrieving data.")

    def perform_create(self, serializer):
        user = self.request.user

        # Only superusers may create a company
        if not user.is_superuser:
            logger.warning(f"Company creation blocked for non-superuser {user.user_id}")
            raise PermissionDenied("Only superusers can create a company.")

        try:
            email = getattr(user, 'user_email', '').strip().lower()

            if not email or "@" not in email:
                logger.warning(f"Invalid email structure for user {user.user_id}")
                raise ValidationError("A valid email address is required to create a company.")

            domain = email.split("@")[-1].lower()
            company_name = self.request.data.get("name")

            if not company_name:
                logger.warning(f"Company name missing in request by user {user.user_id}")
                raise ValidationError("Company name is required.")

            if Company.objects.filter(name__iexact=company_name).exists():
                logger.warning(f"Company name already exists: {company_name}")
                raise ValidationError("Company name already exists.")

            if Company.objects.filter(domain__iexact=domain).exists():
                logger.warning(f"Company domain already exists: {domain}")
                raise ValidationError("A company with this domain registration already exists.")

            company = serializer.save(
                created_by=user,
                domain=domain,
                is_verified=False
            )

            Recruiter.objects.create(
                user=user,
                company=company,
                is_admin=True,
                have_access=True
            )
            logger.info(f"Company and Admin recruiter successfully built by user {user.user_id}")

        except (ValidationError, PermissionDenied):
            raise
        except IntegrityError as e:
            logger.critical(f"Database Integrity violation during company creation by user {user.user_id}: {str(e)}")
            raise ValidationError("Database conflict: Ensure profile details are unique.")
        except Exception as e:
            logger.error(f"Fail-safe hit during company creation for user {user.user_id}: {str(e)}", exc_info=True)
            raise APIException("Could not complete company creation process.")

    def update(self, request, *args, **kwargs):
        # Only superusers may edit
        if not request.user.is_superuser:
            logger.warning(f"Unauthorized update blocked for user {request.user.user_id}")
            return Response({
                "success": False,
                "message": "Only superusers can modify company details."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            company = self.get_object()

            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(company, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.info(f"Company record updated successfully by superuser {request.user.user_id}")
            return Response({
                "success": True,
                "message": "Company updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"success": False, "message": "Target company file not found."},
                            status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"success": False, "errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Critical error updating company via user {request.user.user_id}: {str(e)}", exc_info=True)
            return Response({"success": False, "message": "Internal error handling updates."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Only superusers may delete
        if not request.user.is_superuser:
            logger.warning(f"Unauthorized delete attempt by user {request.user.user_id}")
            return Response({
                "success": False,
                "message": "Only superusers can delete a company."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            company = self.get_object()
            company.delete()
            logger.info(f"Company deleted successfully by superuser {request.user.user_id}")
            return Response({
                "success": True,
                "message": "Company deleted successfully"
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"success": False, "message": "Target company records could not be found."},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Critical purge fault on user {request.user.user_id}: {str(e)}", exc_info=True)
            return Response({"success": False, "message": "System error processing data removal."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecruiterViewSet(viewsets.ModelViewSet):
    serializer_class = RecruiterSerializer
    permission_classes = [IsAuthenticated, HasCompanyAccess]
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def create(self, request, *args, **kwargs):
        user = request.user
        email = getattr(user, 'user_email', '').strip().lower()

        if not email or "@" not in email:
            logger.warning(f"Invalid email verification string for user {user.user_id}")
            return Response({"success": False, "message": "A valid institutional email is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        domain = email.split("@")[-1]
        company = Company.objects.filter(domain__iexact=domain).first()

        if not company:
            return Response({"success": False, "message": "No registered enterprise profile found."},
                            status=status.HTTP_404_NOT_FOUND)

        if Recruiter.objects.filter(user=request.user).exists():
            return Response({"success": False, "message": "A recruiter profile mapping already exists."},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, company=company, have_access=False, is_admin=False)

        logger.info(f"Recruiter tracking identity completed cleanly for user {request.user.user_id}")
        return Response({"success": True, "message": "Profile created", "data": serializer.data},
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Allows the logged-in user to fetch or update their profile without knowing their PK"""
        recruiter = Recruiter.objects.filter(user=request.user).first()

        if not recruiter:
            return Response({"message": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            serializer = self.get_serializer(recruiter)
            return Response(serializer.data, status=status.HTTP_200_OK)

        try:
            serializer = self.get_serializer(recruiter, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({
                "success": True,
                "message": "Profile updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"success": False, "errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        recruiter = self.get_object()
        serializer = self.get_serializer(recruiter)
        logger.info(f"Details viewed by user {request.user.user_id}")
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        recruiter = self.get_object()
        partial = kwargs.pop('partial', False)

        serializer = self.get_serializer(recruiter, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Details updated successfully by user {request.user.user_id}")
        return Response({"success": True, "message": "Recruiter updated successfully", "data": serializer.data},
                        status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        recruiter = self.get_object()
        recruiter.delete()

        logger.info(f"Recruiter deleted successfully by user {request.user.user_id}")
        return Response({"success": True, "message": "Records deleted successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='give-access')
    def give_access(self, request, pk=None):
        company = self.get_object().company

        is_admin = Recruiter.objects.filter(
            user=request.user, company=company, is_admin=True, have_access=True
        ).exists()
        if not is_admin:
            return Response({"success": False, "message": "Admin privileges required."},
                            status=status.HTTP_403_FORBIDDEN)

        user_email = request.data.get("user_email", "").strip().lower()
        # FIX: field is user_email on your Users model, not email
        recruiter = Recruiter.objects.filter(user__user_email=user_email, company=company).first()

        if not recruiter:
            return Response({"success": False, "message": "Target recruiter not found in company."},
                            status=status.HTTP_404_NOT_FOUND)

        recruiter.have_access = True
        recruiter.save()
        # FIX: primary key is recruiter_id, not id
        logger.info(f"Access granted to recruiter {recruiter.recruiter_id} via operator {request.user.user_id}")
        return Response({"success": True, "message": "Access granted successfully"}, status=status.HTTP_200_OK)
