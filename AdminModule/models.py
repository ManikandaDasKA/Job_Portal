from django.db import models
from django.conf import settings


class AdminProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )

    admin_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_profile'
    )
    full_name = models.CharField(max_length=255, blank=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)

    # Granular permission toggles
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_profiles'
        ordering = ['full_name']
        verbose_name = 'Admin Profile'
        verbose_name_plural = 'Admin Profiles'
        indexes = [
            models.Index(fields=['full_name'])
        ]

    def __str__(self):
        return f"{self.full_name or self.user.user_email} ({self.get_admin_level_display()})"