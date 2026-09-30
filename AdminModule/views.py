from rest_framework import status
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from Users.authentication import CustomJWTAuthentication
from Users.permissions import IsAdminUserRole

from notification.helpers import notify_user

from recruiter.models import Company

import logging

logger = logging.getLogger(__name__)

class PendingRecruiterCompaniesView(APIView):
    """
    Returns full details of all companies awaiting admin verification,
    along with the primary recruiter/creator details from the Recruiter model.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        try:
            pending_companies = (
                Company.objects.filter(is_verified=False)
                .prefetch_related('recruiters__user')
                .order_by('-created_at')
            )

            results = []
            for company in pending_companies:
                primary_recruiter = (
                    company.recruiters.filter(is_admin=True).first()
                    or company.recruiters.first()
                )
                recruiter_user = primary_recruiter.user if primary_recruiter else None

                results.append({
                    "company_id": getattr(company, 'company_id', getattr(company, 'id', None)),
                    "company_name": getattr(company, 'name', 'N/A'),
                    "industry": getattr(company, 'industry', 'N/A'),
                    "company_email": getattr(company, 'email', getattr(company, 'contact_email', 'N/A')),
                    "location": getattr(company, 'location', 'N/A'),
                    "address": getattr(company, 'address', 'N/A'),
                    "description": getattr(company, 'description', ''),
                    "is_verified": company.is_verified,
                    "company_created_at": (
                        company.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if getattr(company, 'created_at', None) else "N/A"
                    ),

                    "recruiter_id": primary_recruiter.recruiter_id if primary_recruiter else None,
                    "recruiter_user_id": (
                        getattr(recruiter_user, 'user_id', recruiter_user.pk) if recruiter_user else None
                    ),
                    "recruiter_name": primary_recruiter.full_name if primary_recruiter else "N/A",
                    "recruiter_email": (
                        getattr(recruiter_user, 'user_email', getattr(recruiter_user, 'email', 'N/A'))
                        if recruiter_user else "N/A"
                    ),
                    "recruiter_phone": primary_recruiter.phone_number if primary_recruiter else "N/A",
                    "recruiter_designation": primary_recruiter.designation if primary_recruiter else "N/A",
                    "recruiter_gender": primary_recruiter.get_gender_display() if primary_recruiter else "N/A",
                    "is_company_admin": primary_recruiter.is_admin if primary_recruiter else False,
                    "have_access": primary_recruiter.have_access if primary_recruiter else False,
                    "recruiter_registered_at": (
                        primary_recruiter.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if primary_recruiter else "N/A"
                    ),
                })

            return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to retrieve pending companies: {str(e)}", exc_info=True)
            return Response({"error": "Failed to retrieve pending companies."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminCompanyVerifyActionView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request, pk):
        action = request.data.get("action")  # 'approve' or 'reject'
        company = Company.objects.filter(pk=pk).first()

        if not company:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)

        primary_recruiter = (
            company.recruiters.filter(is_admin=True).first()
            or company.recruiters.first()
        )

        if action == "approve":
            company.is_verified = True
            company.save()

            if primary_recruiter:
                primary_recruiter.have_access = True
                primary_recruiter.save()

                user = primary_recruiter.user
                user.is_verified = True
                user.save()

                notify_user(
                    recipient=user,
                    title="Company Account Approved",
                    message=f"Your company '{company.name}' has been verified. You now have full access to post jobs and review candidates.",
                    notification_type="system",
                    send_email=True
                )

            return Response({"message": f"Company '{company.name}' approved successfully."},
                            status=status.HTTP_200_OK)

        elif action == "reject":
            if primary_recruiter:
                primary_recruiter.have_access = False
                primary_recruiter.save()
                primary_recruiter.user.is_active = False
                primary_recruiter.user.save()

            return Response({"message": f"Company '{company.name}' registration was rejected."},
                            status=status.HTTP_200_OK)

        return Response({"error": "Invalid action. Use 'approve' or 'reject'."},
                        status=status.HTTP_400_BAD_REQUEST)