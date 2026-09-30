from celery import uuid
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from django.conf import settings
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower
from recruiter.models import Company

class TimeStampedModel(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Category(TimeStampedModel):

    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        db_table = "categories"
        ordering = ["name"]
        verbose_name_plural = "Categories"
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="unique_category_name_ci"
            )
        ]

    def save(self, *args, **kwargs):

        self.name = self.name.strip().title()
        self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Job(TimeStampedModel):

    class WorkType(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Full Time"
        PART_TIME = "PART_TIME", "Part Time"

    class WorkMode(models.TextChoices):
        ONSITE = "ONSITE", "Onsite"
        REMOTE = "REMOTE", "Remote"
        HYBRID = "HYBRID", "Hybrid"

    class EmploymentType(models.TextChoices):
        PERMANENT = "PERMANENT", "Permanent"
        CONTRACT = "CONTRACT", "Contract"
        FREELANCE = "FREELANCE", "Freelance"
        INTERNSHIP = "INTERNSHIP", "Internship"

    class ExperienceLevel(models.TextChoices):
        FRESHER = "FRESHER", "Fresher"
        JUNIOR = "JUNIOR", "Junior"
        MID = "MID", "Mid Level"
        SENIOR = "SENIOR", "Senior"
        LEAD = "LEAD", "Lead"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        EXPIRED = "EXPIRED", "Expired"

    job_id = models.AutoField(primary_key=True)

    recruiter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name="jobs")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL,null=True,related_name="jobs")

    title = models.CharField(max_length=200)
    title_slug = models.SlugField(max_length=250, blank=True)
    description = models.TextField()
    location = models.CharField(max_length=150, blank=True)
    work_type = models.CharField(max_length=20, choices=WorkType.choices, default=WorkType.FULL_TIME)
    work_mode = models.CharField(max_length=20, choices=WorkMode.choices, default=WorkMode.ONSITE)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.PERMANENT)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.MID)
    years_of_experience = models.PositiveIntegerField(default=0)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    skills_required = models.JSONField(default=list, blank=True, help_text="Example: ['Python', 'Django', 'PostgreSQL']")
    tags = models.JSONField(default=list, blank=True, help_text="Example: ['backend', 'api', 'developer']")
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    vacancies = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["work_type"]),
            models.Index(fields=["work_mode"]),
            models.Index(fields=["employment_type"]),
            models.Index(fields=["experience_level"]),
            models.Index(fields=["years_of_experience"]),
            models.Index(fields=["created_at"]),
        ]

        constraints = [
            UniqueConstraint(fields=['title_slug'], name='unique_job_title_slug')
        ]

    def save(self, *args, **kwargs):
        """
        Generates clean slugs instantly in local execution memory 
        without introducing blocking database loop lookups.
        """
        if not self.title_slug:
            base_slug = slugify(self.title)
            # ✅ HIGH CONCURRENCY FIXED: Appends an instant 6-character unique hex value 
            # to prevent race condition duplicates without any blocking ORM calls.
            unique_suffix = uuid()[:6]
            self.title_slug = f"{base_slug}-{unique_suffix}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def salary_range(self):
        if self.salary_min and self.salary_max:
            return f"{self.salary_min} - {self.salary_max}"
        return "Not Disclosed"