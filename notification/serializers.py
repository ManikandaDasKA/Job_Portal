from rest_framework import serializers
from django.utils.timesince import timesince
from django.utils import timezone
from .models import Notification

def format_human_readable_time(created_at):
    """
    Helper function to format database timestamps into clean, 
    human-readable intervals like '3 hours ago' or '1 week ago'.
    """
    if not created_at:
        return "Just now"
        
    # timesince() can return things like "1 week, 2 days". 
    # Splitting by comma ensures we just get the most prominent unit ("1 week").
    delta_string = timesince(created_at, timezone.now()).split(',')[0]
    return f"{delta_string} ago"


class NotificationListSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        # ✅ FIXED: Changed "id" to "notification_id" to match your actual model field
        fields = ["notification_id", "message", "time"]

    def get_time(self, obj):
        return format_human_readable_time(obj.created_at)


class NotificationSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        # ✅ FIXED: Changed "id" to "notification_id" to match your actual model field
        fields = [
            "notification_id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "read_at",
            "time"
        ]

    def get_time(self, obj):
        return format_human_readable_time(obj.created_at)