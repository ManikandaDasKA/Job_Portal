# tests/conftest.py

import pytest
from rest_framework.test import APIClient
from channels.testing import WebsocketCommunicator

from notification.models import Notification
from Users.models import Users


# ---------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------

@pytest.fixture
def api_client():
    """Returns an unauthenticated DRF APIClient."""
    return APIClient()


# ---------------------------------------------------------------------
# User Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def user(db):
    """Creates a normal authenticated user."""

    return Users.objects.create_user(
        user_email="user@test.com",
        password="Password@123"
    )


@pytest.fixture
def second_user(db):
    """Creates another user."""

    return Users.objects.create_user(
        user_email="second@test.com",
        password="Password@123"
    )


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated DRF API client."""

    api_client.force_authenticate(user=user)

    return api_client


# ---------------------------------------------------------------------
# Notification Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def notification(user):
    """Unread notification."""

    return Notification.objects.create(
        recipient=user,
        title="Test Notification",
        message="This is a notification.",
        notification_type="system",
        is_read=False,
    )


@pytest.fixture
def read_notification(user):
    """Already read notification."""

    return Notification.objects.create(
        recipient=user,
        title="Read Notification",
        message="Already read",
        notification_type="system",
        is_read=True,
    )


@pytest.fixture
def notification_list(user):
    """Creates multiple notifications."""

    notifications = []

    for i in range(5):
        notifications.append(
            Notification.objects.create(
                recipient=user,
                title=f"Notification {i}",
                message=f"Message {i}",
                notification_type="system",
                is_read=False,
            )
        )

    return notifications


@pytest.fixture
def empty_notifications(user):
    """Ensures the user has no notifications."""

    Notification.objects.filter(recipient=user).delete()

    return user


# ---------------------------------------------------------------------
# Serializer Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def notification_payload():
    return {
        "title": "Job Alert",
        "message": "New Python Developer Job",
        "notification_type": "job_alert",
        "data": {
            "job_id": "123"
        }
    }


# ---------------------------------------------------------------------
# WebSocket Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def websocket_path():
    """
    Change this path to match your routing.py.
    Example:
        ws://localhost/ws/notifications/
    """

    return "/ws/notifications/"


@pytest.fixture
def invalid_websocket_path():
    return "/ws/notifications/?token=invalidtoken"


# ---------------------------------------------------------------------
# Celery Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def email_data():

    return {
        "recipient_email": "user@test.com",
        "subject": "Welcome",
        "message": "Hello User"
    }


# ---------------------------------------------------------------------
# Signal Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def unread_notification(user):

    return Notification.objects.create(
        recipient=user,
        title="Unread",
        message="Unread Message",
        notification_type="system",
        is_read=False
    )


@pytest.fixture
def read_notification_signal(user):

    notification = Notification.objects.create(
        recipient=user,
        title="Read",
        message="Read Message",
        notification_type="system",
        is_read=True
    )

    return notification