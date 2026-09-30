from django.urls import path
from .views import JobApplicationCreateListView, ApplicationDetailView, ApplicationListView, ApplicationDetailViewData

app_name = 'applications'

urlpatterns = [
    path('apply/', ApplicationListView.as_view(), name='job-apply'),
    # GET: List my applications | POST: Apply for a job
    path('apply/data/', JobApplicationCreateListView.as_view(), name='job-apply-data'),
    
    # GET: View specific application details
    path('apply/<int:application_id>/', ApplicationDetailView.as_view(), name='application-detail'),
    path('apply/<int:application_id>/data/', ApplicationDetailViewData.as_view(), name='application-detail-data'),

    # path('api/jobs/<int:job_id>/apply/', ApplyForJobAPIView.as_view(), name='api_apply_for_job'),
]