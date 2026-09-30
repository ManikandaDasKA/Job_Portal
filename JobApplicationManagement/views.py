from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from Users.authentication import CustomJWTAuthentication
from .models import Application, Job
from .serializers import ApplicationSerializer
from jobseeker.models import JobSeekerProfile
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

class ApplicationListView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return render(request, 'applicationListView.html')

class JobApplicationCreateListView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return a list of all applications the current user has made.
        """
        return Application.objects.filter(jobseeker__user=self.request.user).select_related('job', 'job__company')

    def perform_create(self, serializer):
        """
        Automatically link the logged-in user's profile to the application.
        """
        profile = JobSeekerProfile.objects.get(user=self.request.user)
        serializer.save(jobseeker=profile)

class ApplicationDetailView(APIView): 
    permission_classes = [AllowAny]   
    def get(self, request, application_id): 
        return render(self.request, 'applicationDetailView.html')   

class ApplicationDetailViewData(generics.RetrieveAPIView):
    """
    View a specific application detail.
    """
    authentication_classes = [JWTAuthentication]
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'application_id'

class ApplyForJobAPIView(APIView):
    """
    Dedicated endpoint to apply for a specific job.
    Expects a POST request to /api/jobs/<job_id>/apply/
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        # 1. Fetch the logged-in user's JobSeekerProfile
        try:
            profile = JobSeekerProfile.objects.get(user=request.user)
        except JobSeekerProfile.DoesNotExist:
            return Response(
                {"error": "You must complete your job seeker profile before applying."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Fetch the specific job they are applying to
        # Note: replace 'job_id' with your actual primary key field name if it differs (e.g., 'id' or 'pk')
        job = get_object_or_404(Job, pk=job_id) 

        # 3. Prevent duplicate applications
        if Application.objects.filter(jobseeker=profile, job=job).exists():
            return Response(
                {"error": "You have already applied for this position."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Process the application via the serializer
        # This allows the frontend to pass extra data (like a cover letter) in request.data
        serializer = ApplicationSerializer(data=request.data)
        
        if serializer.is_valid():
            # Force the jobseeker and job fields to ensure they can't be spoofed by the frontend
            serializer.save(jobseeker=profile, job=job)
            return Response(
                {
                    "message": "Application submitted successfully!",
                    "data": serializer.data
                }, 
                status=status.HTTP_201_CREATED
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)