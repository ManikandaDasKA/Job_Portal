from django.db import models
from django.conf import settings
from Jobs.models import Job
from jobseeker.models import JobSeekerProfile


# Create your models here.
class Application(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    )
    application_id = models.AutoField(primary_key=True)  # ✅ Custom PK
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    jobseeker = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name='my_applications')
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    applied_at = models.DateTimeField(auto_now_add=True)