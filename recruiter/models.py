from django.db import models
from django.conf import settings

class Company(models.Model):
    """
    Stores company details.
    """
    company_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255,unique=True,db_index=True)
    domain = models.CharField(max_length=100,blank=False,db_index=True)
    description = models.TextField(blank=True)
    website = models.URLField(max_length=200,blank=True,null=True, unique=True)
    location = models.CharField(max_length=255,db_index=True)
    address = models.TextField(blank=True)
    industry = models.CharField(max_length=100,blank=True,db_index=True)
    is_verified = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='companies_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        
        db_table = "companies"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["name"]),
            models.Index(fields=["industry"]),
            models.Index(fields=["location"]),
        ]

    def __str__(self):
        return self.name

class Recruiter(models.Model):

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )

    recruiter_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='recruiter_profile')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='recruiters')
    full_name = models.CharField(max_length=300, db_index=True, blank=True)
    designation = models.CharField(max_length=100,blank=True)
    phone_number = models.CharField(max_length=15,blank=True,null=True)
    gender = models.CharField(max_length=10,choices=GENDER_CHOICES,blank=True)
    is_admin = models.BooleanField(default=False)
    have_access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'company']
        db_table = "recruiters"
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["designation"]),
            models.Index(fields=["is_admin"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.company.name}"