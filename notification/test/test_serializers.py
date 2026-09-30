# tests/test_serializers.py

import pytest
from django.utils import timezone
from datetime import timedelta

from notification.models import Notification
from notification.serializers import (
    format_human_readable_time,
    NotificationListSerializer,
    NotificationSerializer,
)

pytestmark = pytest.mark.django_db


class TestFormatHumanReadableTime:

    # ---------------------------------------------------------
    # None timestamp
    # ---------------------------------------------------------

    def test_format_time_none(self):
        """
        Should return 'Just now'
        when created_at is None.
        """

        assert format_human_readable_time(None) == "Just now"

    # ---------------------------------------------------------
    # Valid timestamp
    # ---------------------------------------------------------

    def test_format_time(self):
        """
        Verify formatted time string.
        """

        created_at = timezone.now() - timedelta(minutes=10)

        result = format_human_readable_time(created_at)

        assert "ago" in result


class TestNotificationListSerializer:

    # ---------------------------------------------------------
    # get_time()
    # ---------------------------------------------------------

    def test_get_time(self, notification):

        serializer = NotificationListSerializer(notification)

        assert "ago" in serializer.data["time"]

    # ---------------------------------------------------------
    # Output fields
    # ---------------------------------------------------------

    def test_serializer_fields(self, notification):

        serializer = NotificationListSerializer(notification)

        assert "notification_id" in serializer.data
        assert "message" in serializer.data
        assert "time" in serializer.data

        assert len(serializer.data) == 3

    # ---------------------------------------------------------
    # many=True
    # ---------------------------------------------------------

    def test_many_serializer(self, notification_list):

        serializer = NotificationListSerializer(
            notification_list,
            many=True,
        )

        assert len(serializer.data) == len(notification_list)

    # ---------------------------------------------------------
    # Empty queryset
    # ---------------------------------------------------------

    def test_empty_queryset(self):

        serializer = NotificationListSerializer(
            [],
            many=True,
        )

        assert serializer.data == []


class TestNotificationSerializer:

    # ---------------------------------------------------------
    # get_time()
    # ---------------------------------------------------------

    def test_get_time(self, notification):

        serializer = NotificationSerializer(notification)

        assert "ago" in serializer.data["time"]

    # ---------------------------------------------------------
    # Output fields
    # ---------------------------------------------------------

    def test_serializer_fields(self, notification):

        serializer = NotificationSerializer(notification)

        expected_fields = {
            "notification_id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "read_at",
            "time",
        }

        assert set(serializer.data.keys()) == expected_fields

    # ---------------------------------------------------------
    # Verify values
    # ---------------------------------------------------------

    def test_serializer_values(self, notification):

        serializer = NotificationSerializer(notification)

        assert serializer.data["title"] == notification.title
        assert serializer.data["message"] == notification.message
        assert (
            serializer.data["notification_type"]
            == notification.notification_type
        )
        assert (
            serializer.data["is_read"]
            == notification.is_read
        )

    # ---------------------------------------------------------
    # Read notification
    # ---------------------------------------------------------

    def test_read_notification_serializer(self, read_notification):

        serializer = NotificationSerializer(read_notification)

        assert serializer.data["is_read"] is True

    # ---------------------------------------------------------
    # many=True
    # ---------------------------------------------------------

    def test_many_serializer(self, notification_list):

        serializer = NotificationSerializer(
            notification_list,
            many=True,
        )

        assert len(serializer.data) == len(notification_list)

    # ---------------------------------------------------------
    # Empty queryset
    # ---------------------------------------------------------

    def test_empty_queryset(self):

        serializer = NotificationSerializer(
            [],
            many=True,
        )

        assert serializer.data == []