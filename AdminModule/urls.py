from django.urls import path
from .views import PendingRecruiterCompaniesView, AdminCompanyVerifyActionView

app_name = "admin-module"

urlpatterns = [
    path('api/v1/admin/pending-recruiters/', PendingRecruiterCompaniesView.as_view(), name='admin_pending_recruiters'),
    path('api/v1/admin/companies/<int:pk>/verify/', AdminCompanyVerifyActionView.as_view(), name='admin_verify_company'),
]