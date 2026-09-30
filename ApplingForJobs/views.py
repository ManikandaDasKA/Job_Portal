import logging
from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist

from asgiref.sync import async_to_sync
from notification.helpers import notify_user

from Users.authentication import CustomJWTAuthentication

from jobseeker.models import JobSeekerProfile
from Jobs.models import Job
from JobApplicationManagement.models import Application

from Jobs.serializers import JobListSerializer

logger = logging.getLogger(__name__)

class JobSearchUIView(APIView):
    """Renders the HTML page for the Job Search Interface"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return render(request, 'job_search.html')

class AppliedCandidatesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, job_id):
        return render(request, 'applied_candidates.html', {"job_id": job_id})
    
class SuggestedJobsAPIView(generics.ListAPIView):
    """
    API 1: Returns jobs where AT LEAST ONE skill matches the user's profile.
    """
    serializer_class = JobListSerializer 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Job.objects.filter(status='OPEN').select_related('category', 'company')
        try:
            skills_queryset = self.request.user.jobseeker_profile.skills.values_list('skill_name', flat=True)
            user_skills = list(skills_queryset)
            
            if user_skills and len(user_skills) > 0:
                skill_query = Q()
                for skill in user_skills:
                    skill_query |= Q(skills_required__icontains=skill.strip())
                
                return queryset.filter(skill_query).distinct()
                
        except (AttributeError, ObjectDoesNotExist):
            pass
            
        return Job.objects.none()
    
class FilterJobsAPIView(generics.ListAPIView):
    """
    API 2: Standard search and filtering based on user inputs (Keywords, Location, etc.)
    """
    serializer_class = JobListSerializer 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category__name', 'company__location', 'work_type']
    search_fields = ['title', 'description', 'company__name']
    ordering_fields = ['created_at', 'salary_min', 'salary_max']
    ordering = ['-created_at'] 

    def get_queryset(self):
        return Job.objects.filter(status='OPEN').select_related('category', 'company')


class ApplyForJobAPIView(APIView):
    """
    Optimized endpoint to apply for a specific job with transaction safety and real-time triggers.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic 
    def post(self, request, job_id):
        logger.info(f"--- APPLY VIEW TRIGGERED FOR JOB ID: {job_id} ---")
        
        # 1. Fetch user profile cleanly
        profile = JobSeekerProfile.objects.filter(user=request.user).first()
        if not profile:
            logger.warning(f"Application blocked: User {request.user.id} has no completed profile.")
            return Response(
                {"error": "You must complete your job seeker profile before applying."}, 
                status=status.HTTP_403_FORBIDDEN 
            )

        # 2. Fetch the job, ensuring it is actually open for applications
        try:
            # select_related recruiter so we have the user instance for notifications without extra queries
            job = Job.objects.select_related('recruiter').get(job_id=job_id, status='OPEN')
        except Job.DoesNotExist:
            return Response(
                {"error": "This job does not exist or is no longer accepting applications."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Prevent duplicate applications
        already_applied = Application.objects.filter(job=job, jobseeker=profile).exists()
        if already_applied:
            return Response(
                {"error": "You have already applied for this job."}, 
                status=status.HTTP_409_CONFLICT
            )
            
        # 4. Create the application row entry inside our database transaction block
        application = Application.objects.create(
            job=job,
            jobseeker=profile,
            status='APPLIED' 
        )
        
        # 5. 🌟 REAL-TIME NOTIFICATION TRIGGERS
        # Since this view is synchronous (`def post`) but our `notify_user` system is non-blocking,
        # we safely invoke it using `async_to_sync` wrappers.
        try:
            # A) Notify the RECRUITER who listed the job
            async_to_sync(notify_user)(
                recipient=job.recruiter,
                title="New Application Received! 📄",
                message=f"A candidate has applied for your listing '{job.title}'.",
                notification_type="application",
                data={
                    "job_id": str(job.job_id),
                    "application_id": str(application.id) if hasattr(application, 'id') else None
                }
            )

            # B) Notify the JOB SEEKER confirming their submission
            async_to_sync(notify_user)(
                recipient=request.user,
                title="Application Submitted 🟢",
                message=f"Your application for '{job.title}' was submitted successfully!",
                notification_type="system",
                data={
                    "job_id": str(job.job_id)
                }
            )
            logger.info(f"[Application Notifications] Successfully dispatched real-time alerts for job_id={job_id}")

        except Exception as notify_err:
            # We catch this in a separate block so if a notification fails, 
            # it doesn't crash or rollback the user's actual job application transaction!
            logger.error(f"[Application Notifications Failure] Non-fatal delivery disruption: {str(notify_err)}")

        return Response(
            {"message": "Your application was submitted successfully!"}, 
            status=status.HTTP_201_CREATED
        )

class AppliedCandidatesDataView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        user = request.user
        profile = getattr(user, 'recruiter_profile', None)

        if not profile:
            return Response({"detail": "Profile missing"}, status=404)

        try:
            # We use job_id=job_id here because your model uses 'job_id' as the field name
            job = Job.objects.get(job_id=job_id, recruiter=user)
        except Job.DoesNotExist:
            return Response({"detail": "Job not found or unauthorized"}, status=404)

        applications = Application.objects.filter(job=job).select_related('jobseeker__user')

        candidates_data = []
        for app in applications:
            candidates_data.append({
                "application_id": app.application_id,
                "candidate_name": app.jobseeker.full_name if app.jobseeker else "N/A",
                "candidate_email": app.jobseeker.user.user_email if app.jobseeker and app.jobseeker.user else "N/A",
                "status": app.get_status_display(),
                "applied_at": app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "N/A"
            })

        return Response({
            "job_title": job.title,
            "candidates": candidates_data
        })