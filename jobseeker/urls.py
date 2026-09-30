from django.urls import path
from .views import *

app_name = 'jobseeker'

urlpatterns = [
    path('interface/', jobseeker_dashboard_view, name='jobseeker-profile-interface'),
    # path('dashboard/', jobseeker_dashboard_view, name='jobseeker-dashboard'),

    path('profile/', JobSeekerProfileView.as_view(), name='jobseeker-profile'),

    path('profile/skill/', SkillView.as_view()),
    path('profile/skill/<int:skill_id>/', SkillView.as_view()),

    path('profile/location/', PreferredLocationView.as_view(), name='jobseeker-location'),
    path('profile/location/<int:location_id>/', PreferredLocationView.as_view()),

    path('profile/education/', EducationView.as_view(), name='jobseeker-education'),
    path('profile/education/<int:education_id>/', EducationView.as_view()),

    path('profile/experience/', ExperienceView.as_view(), name='jobseeker-experience'),
    path('profile/experience/<int:experience_id>/', ExperienceView.as_view()),
]