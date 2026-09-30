from rest_framework import serializers
from .models import Application

class ApplicationSerializer(serializers.ModelSerializer):
    # We display related details but keep them read-only for the POST request
    job_title = serializers.ReadOnlyField(source='job.title')
    company_name = serializers.ReadOnlyField(source='job.company.name')
    category = serializers.ReadOnlyField(source='job.category.name')
     #----------------------------------------------------------        
    description = serializers.ReadOnlyField(source='job.description')
    location = serializers.ReadOnlyField(source='job.location')
    job_type = serializers.ReadOnlyField(source='job.job_type')
    experience_level = serializers.ReadOnlyField(source='job.experience_level')
    salary_min = serializers.ReadOnlyField(source='job.salary_min')
    salary_max = serializers.ReadOnlyField(source='job.salary_max')
    skills_required = serializers.ReadOnlyField(source='job.skills_required')

    class Meta:
        model = Application
        fields = [
            'application_id', 'job', 'jobseeker', 'job_title', 'category', 'description', 'location', 'job_type', 'experience_level', 
            'salary_min', 'salary_max', 'skills_required',
            'company_name', 'resume', 'cover_letter', 'status', 'applied_at'
        ]
        read_only_fields = ['status', 'applied_at', 'jobseeker']

    def validate(self, data):
        """Check if the user has already applied for this job."""
        user = self.context['request'].user
        job = data.get('job')
        
        # We check if an application already exists for this specific profile and job
        if Application.objects.filter(jobseeker__user=user, job=job).exists():
            raise serializers.ValidationError("You have already applied for this job.")
        return data