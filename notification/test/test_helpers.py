import pytest
from unittest.mock import MagicMock, patch

from notification.helpers import notify_user


pytestmark = pytest.mark.django_db


@patch("notification.helper.NotificationService.create_notification")
@patch("notification.helper.send_email_notification_task.delay")
def test_notify_without_email(
    mock_delay,
    mock_create_notification,
    user,
):
    notification = MagicMock()
    notification.title = "Hello"

    mock_create_notification.return_value = notification

    result = notify_user(
        recipient=user,
        title="Hello",
        message="Welcome",
    )

    assert result == notification

    mock_create_notification.assert_called_once_with(
        recipient=user,
        title="Hello",
        message="Welcome",
        notification_type="system",
        data={},
    )

    mock_delay.assert_not_called()


@patch("notification.helper.NotificationService.create_notification")
@patch("notification.helper.send_email_notification_task.delay")
def test_notify_with_email(
    mock_delay,
    mock_create_notification,
    user,
):
    notification = MagicMock()

    mock_create_notification.return_value = notification

    notify_user(
        recipient=user,
        title="Hello",
        message="Welcome",
        send_email=True,
    )

    mock_create_notification.assert_called_once()

    mock_delay.assert_called_once_with(
        recipient_email=user.user_email,
        subject="Hello",
        message="Welcome",
    )


@patch("notification.helper.NotificationService.create_notification")
def test_notify_with_custom_type(
    mock_create_notification,
    user,
):
    notify_user(
        recipient=user,
        title="Interview",
        message="Interview Scheduled",
        notification_type="interview",
    )

    mock_create_notification.assert_called_once_with(
        recipient=user,
        title="Interview",
        message="Interview Scheduled",
        notification_type="interview",
        data={},
    )


@patch("notification.helper.NotificationService.create_notification")
def test_notify_with_data(
    mock_create_notification,
    user,
):
    payload = {"job_id": "101"}

    notify_user(
        recipient=user,
        title="Job",
        message="Applied",
        data=payload,
    )

    mock_create_notification.assert_called_once_with(
        recipient=user,
        title="Job",
        message="Applied",
        notification_type="system",
        data=payload,
    )