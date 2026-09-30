import uuid

from django.db import models
from django.conf import settings


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        APPLICATION = 'application', 'Application'
        INTERVIEW = 'interview', 'Interview'
        JOB_ALERT = 'job_alert', 'Job Alert'
        SYSTEM = 'system', 'System'
        MESSAGE = 'message', 'Message'

    notification_id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50,choices=NotificationType.choices)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True,blank=True)
    data = models.JSONField(default=dict,blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.title}'