from django.urls import path
from .views import CompanyProfileTemplate, RecruiterProfileTemplate, admin_page, CompanyViewSet, RecruiterViewSet

app_name = "recruiter"

urlpatterns = [
    path('companies/', CompanyViewSet.as_view({'get': 'list', 'post': 'create'}), name='company-list'),
    path('companies/<int:pk>/', CompanyViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='company-detail'),
    path('', RecruiterViewSet.as_view({'post': 'create'}), name='recruiter-create'),
    path('me/', RecruiterViewSet.as_view({'get': 'me', 'patch': 'me'}), name='recruiter-me'),
    
    path('<int:pk>/', RecruiterViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='recruiter-detail'),
    path('<int:pk>/give-access/', RecruiterViewSet.as_view({'post': 'give_access'}), name='give-access'),

    path('company/profile/', CompanyProfileTemplate, name='company-profile'),
    path('profile/', RecruiterProfileTemplate, name='recruiter-profile'),
    path('admin-dashboard/', admin_page, name='admin_dashboard'),
]