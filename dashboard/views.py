import datetime

from django.utils import timezone
from django.db.models import Count
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.shortcuts import render

from asyncio.log import logger

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from Users.authentication import CustomJWTAuthentication
from Users.permissions import IsAdminUserRole

from notification.helpers import notify_user

from jobseeker.models import JobSeekerProfile

from JobApplicationManagement.models import Application

from Jobs.models import Job

from recruiter.models import Recruiter

User = get_user_model()

class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]  # Allow any user to access this view

    def get(self, request):
        # Just returns the HTML file you created earlier
        return render(request, 'admin_dashboard.html')

class JobSeekerDashboardView(APIView):
    permission_classes = [IsAuthenticated]  # Allow authenticated users to access this view

    def get(self, request):
        # Just returns the HTML file you created earlier
        return render(request, 'jobseeker_dashboard.html')

class jobseekerDashboardDataView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. FIX: The field name is 'user', not 'job'.
        profile = JobSeekerProfile.objects.filter(user=user).first()

        if profile:
            # Base profile fields
            base_fields = [
                bool(profile.full_name),
                bool(profile.headline),
                bool(profile.bio),
                bool(profile.phone_number),
            ]
            
            # Related set checks
            has_skills = profile.skills.exists() if hasattr(profile, 'skills') else False
            has_education = profile.educations.exists() if hasattr(profile, 'educations') else False
            has_experience = profile.experiences.exists() if hasattr(profile, 'experiences') else False

            checks = base_fields + [has_skills, has_education, has_experience]
            
            filled_count = sum(1 for filled in checks if filled)
            total_count = len(checks)
            completion_rate = int((filled_count / total_count) * 100)
            
            # 2. Fetch Applications
            all_apps = Application.objects.filter(jobseeker=profile).select_related('job__company')      
            print(all_apps)  # Debug: Check the generated SQL query
        else:
            # Handle user with no profile gracefully
            logger.error(f"User {user.user_email} has no JobSeekerProfile.")
            completion_rate = 0
            all_apps = Application.objects.none() 

        # 3. Stats Breakdown
        status_counts = {
            "total_applied": all_apps.count(),
            "total_pending": all_apps.filter(status='Pending').count(),
            "total_accepted": all_apps.filter(status='Accepted').count(),
            "total_rejected": all_apps.filter(status='Rejected').count(),
        }

        # Helper to format data for JSON serialization
        def format_apps(queryset):
            data = []
            for app in queryset:
                data.append({
                    "application_id": app.application_id,
                    "job_title": app.job.title,
                    "category": app.job.category.name if app.job.category else "N/A",
                    "company": app.job.company.name if app.job.company else "N/A",
                    "status": app.get_status_display(),
                    # Date formatting ensures JSON compatibility
                    "date": app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "N/A"
                })
            return data

        return Response({
            "user": profile.full_name if profile else user.user_email,
            "profile_completion": completion_rate,
            "counts": status_counts,
            # FIX: Use the helper function here to serialize the queryset
            "all_applications": format_apps(all_apps.order_by('-applied_at')[:5]),
            "profile_missing": profile is None 
        })
    
class RecruiterDashboardDataView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Safely fetch the recruiter profile
        profile = Recruiter.objects.filter(user=user).select_related('company').first()

        # Strict check: Can this recruiter manage (create/edit) company profiles?
        can_manage_company = bool(user.is_superuser)

        # Handle uninitialized profile gracefully
        if not profile:
            return Response({
                "profile_missing": True,
                "recruiter_profile_completion": 0,
                "company_profile_completion": 0,
                "has_company": False,
                "company_id": None,
                "is_company_admin": False,
                "can_manage_company": can_manage_company,
                "status_summary": {
                    "total_job_postings": 0,
                    "total_applicants_received": 0,
                    "active_postings": 0,
                    "new_this_week": 0,
                },
                "my_job_postings": [],
            }, status=status.HTTP_200_OK)

        # 1. Recruiter Profile Completion
        recruiter_fields = [profile.full_name, profile.designation, profile.phone_number, profile.gender]
        filled_recruiter_fields = [f for f in recruiter_fields if f]
        recruiter_completion_rate = int((len(filled_recruiter_fields) / len(recruiter_fields)) * 100)

        # 2. Company Profile Completion
        company = profile.company
        company_completion_rate = 0
        company_id = None

        if company:
            company_id = getattr(company, 'company_id', getattr(company, 'id', None))
            company_fields = [
                getattr(company, 'name', None), 
                getattr(company, 'description', None), 
                getattr(company, 'website', None), 
                getattr(company, 'location', None),
                getattr(company, 'industry', None),
                getattr(company, 'address', None)
            ]
            filled_company_fields = [f for f in company_fields if f]
            company_completion_rate = int((len(filled_company_fields) / len(company_fields)) * 100)

        # 3. Optimized Job Query
        my_jobs = Job.objects.filter(recruiter=user).select_related('category').annotate(
            num_applicants=Count('applications')
        )
        
        # 4. Stats Summary
        all_apps = Application.objects.filter(job__in=my_jobs)
        status_summary = {
            "total_job_postings": my_jobs.count(),
            "total_applicants_received": all_apps.count(),
            "active_postings": my_jobs.filter(status='open').count(),
            "new_this_week": all_apps.filter(applied_at__gte=timezone.now() - datetime.timedelta(days=7)).count(),
        }

        # 5. Serialized Jobs
        jobs_list = []
        for job in my_jobs:
            jobs_list.append({
                "id": getattr(job, 'job_id', getattr(job, 'id', None)),
                "title": job.title,
                "category": job.category.name if getattr(job, 'category', None) else "N/A",
                "status": job.status,
                "num_applicants": getattr(job, 'num_applicants', 0),
                "created_at": job.created_at.strftime("%b %d, %Y") if job.created_at else "N/A"
            })

        return Response({
            "profile_missing": False,
            "recruiter_profile_completion": recruiter_completion_rate,
            "company_profile_completion": company_completion_rate,
            "has_company": bool(company),
            "company_id": getattr(profile.company, 'company_id', getattr(profile.company, 'id', None)) if profile.company else None,
            "is_company_admin": profile.is_admin,
            "can_manage_company": can_manage_company,
            "status_summary": status_summary,
            "my_job_postings": jobs_list,
        }, status=status.HTTP_200_OK)
    
class AdminDashboardDataView(APIView):
    """
    Returns data for the admin dashboard:
    1. Summary counts (pending approvals, total recruiters, total jobseekers, total jobs)
    2. Pending company registrations awaiting admin review
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        try:
            # 1. Fetch Pending Companies
            # If you have a dedicated Company model with an 'is_verified' or 'status' field:
            # pending_companies = Company.objects.filter(is_verified=False).select_related('owner')
            
            # If your company details are directly associated with Recruiter profiles/User:
            pending_recruiters = User.objects.filter(
                role='recruiter',
                is_verified=False,
                is_active=True
            ).select_related('recruiter_profile')

            results = []
            for user in pending_recruiters:
                profile = getattr(user, 'recruiter_profile', None)
                company = getattr(profile, 'company', None) if profile else None

                company_id = getattr(company, 'id', getattr(company, 'company_id', user.pk))
                company_name = getattr(company, 'name', getattr(user, 'company_name', 'Pending Company'))
                industry = getattr(company, 'industry', 'N/A')
                location = getattr(company, 'location', getattr(company, 'location', 'N/A'))
                address = getattr(company, 'address',  getattr(company, 'address', 'N/A')) 

                results.append({
                    "id": company_id,
                    "user_id": user.user_id if hasattr(user, 'user_id') else user.pk,
                    "company_name": company_name,
                    "industry": industry,
                    "location": location,
                    "address": address,
                    "recruiter_name": profile.full_name if profile and profile.full_name else "N/A",
                    "recruiter_email": user.user_email if hasattr(user, 'user_email') else user.email,
                    "created_at": user.date_joined.strftime("%Y-%m-%d") if hasattr(user, 'date_joined') and user.date_joined else "N/A",
                    "status": "pending"
                })

            # 2. Platform Summary Metrics for Admin Dashboard Cards
            metrics = {
                "pending_approvals": len(results),
                "total_recruiters": User.objects.filter(role='recruiter').count(),
                "total_jobseekers": User.objects.filter(role='jobseeker').count(),
                "total_jobs": Job.objects.count(),
            }

            return Response({
                "metrics": metrics,
                "results": results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Failed to load admin dashboard data: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminCompanyVerifyActionView(APIView):
    """
    Allows the admin to approve or reject a pending recruiter company.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request, pk):
        action = request.data.get("action")  # 'approve' or 'reject'

        if action not in ["approve", "reject"]:
            return Response({"error": "Invalid action. Must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        # Locate the user/company to update
        user = User.objects.filter(pk=pk).first()
        if not user:
            # If pk is company_id, check via recruiter profile
            profile = getattr(user, 'recruiter_profile', None)
            if not profile:
                return Response({"error": "Recruiter account not found."}, status=status.HTTP_404_NOT_FOUND)

        if action == "approve":
            user.is_verified = True
            user.save()

            # If your Company model also has an is_verified flag:
            profile = getattr(user, 'recruiter_profile', None)
            company = getattr(profile, 'company', None) if profile else None
            if company and hasattr(company, 'is_verified'):
                company.is_verified = True
                company.save()

            # Notify the recruiter their account is ready
            notify_user(
                recipient=user,
                title="Company Account Approved",
                message="Your recruiter account and company registration have been approved. You can now post jobs.",
                notification_type="system",
                send_email=True
            )

            return Response({"message": "Company and recruiter approved successfully."}, status=status.HTTP_200_OK)

        elif action == "reject":
            user.is_active = False
            user.save()

            return Response({"message": "Company registration rejected and deactivated."}, status=status.HTTP_200_OK)

class RecruiterDashboardView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return render(request, 'recruiter_dashboard.html')