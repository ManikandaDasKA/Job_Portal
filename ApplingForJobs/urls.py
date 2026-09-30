from django.urls import path
from .views import FilterJobsAPIView, ApplyForJobAPIView, JobSearchUIView, SuggestedJobsAPIView, AppliedCandidatesDataView, AppliedCandidatesView

app_name = 'ApplingForJobs'

urlpatterns = [
    # ... your existing urls ...
    path("search/", JobSearchUIView.as_view(), name='job-search-ui'),
    
    # Jobseeker API Endpoints
    path("suggested/", SuggestedJobsAPIView.as_view(), name="suggested-jobs"),
    
    # Hit this endpoint when the user clicks the "Search" button
    path("job_search/", FilterJobsAPIView.as_view(), name="filter-jobs"),
    path("<int:job_id>/apply/", ApplyForJobAPIView.as_view(), name='api-job-apply'),

    path('<int:job_id>/candidates/', AppliedCandidatesView.as_view(), name='applied-candidates-page'),
    path('<int:job_id>/candidates/data/', AppliedCandidatesDataView.as_view(), name='applied-candidates-data'),
]