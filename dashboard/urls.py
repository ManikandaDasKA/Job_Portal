from django.urls import path
from .views import RecruiterDashboardDataView, JobSeekerDashboardView, RecruiterDashboardView, jobseekerDashboardDataView, AdminDashboardView, AdminDashboardDataView, AdminCompanyVerifyActionView
from dashboard import views

# We define the app name for namespacing
app_name = 'dashboard'

urlpatterns = [
    # Path for the Admin Dashboard
    path('admin/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/data/', views.AdminDashboardDataView.as_view(), name='admin-dashboard-data'),

    # Path for the Jobseeker Dashboard
    path('jobseeker/', JobSeekerDashboardView.as_view(), name='jobseeker-dashboard'),
    path('jobseeker/data/', jobseekerDashboardDataView.as_view(), name='jobseeker-dashboard-data'),
    
    # Path for the Recruiter Dashboard
    path('recruiter/', RecruiterDashboardView.as_view(), name='recruiter-dashboard'),
    path('recruiter/data/', RecruiterDashboardDataView.as_view(), name='recruiter-dashboard-data'),

    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin_dashboard_ui'),

    # Admin Data & Verification Endpoints (Called by admin.html)
    path('api/v1/admin/pending-recruiters/', AdminDashboardDataView.as_view(), name='admin_pending_recruiters_data'),
    path('api/v1/admin/companies/<int:pk>/verify/', AdminCompanyVerifyActionView.as_view(), name='admin_company_verify_action'),
]