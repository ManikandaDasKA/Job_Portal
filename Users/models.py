from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from asgiref.sync import sync_to_async

class UserManager(BaseUserManager):
    def create_user(self, user_email, password=None, **extra_fields):
        if not user_email:
            raise ValueError("Email is required")

        email = self.normalize_email(user_email)
        user = self.model(user_email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, user_email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        return self.create_user(user_email, password, **extra_fields)

    async def acreate_user(self, user_email, password=None, **extra_fields):
        """Asynchronously creates and saves a standard user."""
        return await sync_to_async(self.create_user)(user_email, password=password, **extra_fields)

    async def acreate_superuser(self, user_email, password=None, **extra_fields):
        """Asynchronously creates and saves a superuser."""
        return await sync_to_async(self.create_superuser)(user_email, password=password, **extra_fields)

class Users(AbstractBaseUser,PermissionsMixin):
    ROLE_CHOICES = (
        ('jobseeker', 'JobSeeker'),
        ('recruiter', 'Recruiter'),
        ('admin', 'Admin'),
    )

    user_id = models.AutoField(primary_key=True)
    user_email = models.EmailField(unique=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'user_email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

class UserLoginDetails(models.Model):
    login_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "user_login_details"

# RolePermission model to define permissions for each role and resource
class RolePermission(models.Model):
    ROLE_CHOICES = (
        ('admin',     'Admin'),
        ('jobseeker', 'JobSeeker'),
        ('recruiter', 'Recruiter'),
    )

    RESOURCE_CHOICES = (
        ('jobs',          'Jobs'),
        ('resume',        'Resume & Documents'),
        ('applications',  'Job Applications'),
        ('user',         'user'),
        ('company',       'Company'),
        ('messages',      'Messages'),
        ('notifications', 'Notifications'),
        ('subscriptions', 'Subscriptions'),
    )

    id         = models.AutoField(primary_key=True)
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES)
    resource   = models.CharField(max_length=50, choices=RESOURCE_CHOICES)
    can_read   = models.BooleanField(default=False)
    can_write  = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta:
        db_table       = "role_permissions"
        unique_together = ("role", "resource")
        ordering        = ["role", "resource"]

    def __str__(self):
        return (
            f"{self.role} | {self.resource} | "
            f"R:{self.can_read} W:{self.can_write} D:{self.can_delete}"
        )

