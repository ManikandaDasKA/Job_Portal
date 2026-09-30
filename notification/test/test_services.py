import pytest
from unittest.mock import patch

from notification.models import Notification
from notification.services import NotificationService


pytestmark = pytest.mark.django_db


class TestNotificationService:

    # ---------------------------------------------------------
    # SUCCESS
    # ---------------------------------------------------------

    def test_create_notification_success(self, user):
        """
        Verify notification is created successfully.
        """

        notification = NotificationService.create_notification(
            recipient=user,
            title="Welcome",
            message="Welcome to the platform.",
            notification_type="system",
        )

        assert notification is not None
        assert isinstance(notification, Notification)

        assert notification.recipient == user
        assert notification.title == "Welcome"
        assert notification.message == "Welcome to the platform."
        assert notification.notification_type == "system"

        assert Notification.objects.count() == 1

    # ---------------------------------------------------------
    # DATA FIELD
    # ---------------------------------------------------------

    def test_create_notification_with_data(self, user):
        """
        Verify JSON data is saved correctly.
        """

        payload = {
            "job_id": "123",
            "status": "Applied",
        }

        notification = NotificationService.create_notification(
            recipient=user,
            title="Application Submitted",
            message="Application successful.",
            notification_type="application",
            data=payload,
        )

        assert notification.data == payload

    # ---------------------------------------------------------
    # DEFAULT EMPTY DATA
    # ---------------------------------------------------------

    def test_default_empty_data(self, user):
        """
        Verify default data becomes an empty dict.
        """

        notification = NotificationService.create_notification(
            recipient=user,
            title="System",
            message="Hello",
            notification_type="system",
        )

        assert notification.data == {}

    # ---------------------------------------------------------
    # DATABASE EXCEPTION
    # ---------------------------------------------------------

    @patch("notification.services.Notification.objects.create")
    def test_database_exception(
        self,
        mock_create,
        user,
    ):
        """
        Verify database exception is propagated.
        """

        mock_create.side_effect = Exception("Database Failure")

        with pytest.raises(Exception) as exc:

            NotificationService.create_notification(
                recipient=user,
                title="Test",
                message="Message",
                notification_type="system",
            )

        assert str(exc.value) == "Database Failure"

    # ---------------------------------------------------------
    # LOGGER INFO CALLED
    # ---------------------------------------------------------

    @patch("notification.services.logger")
    def test_logger_info_called(
        self,
        mock_logger,
        user,
    ):
        """
        Verify info logger is called.
        """

        NotificationService.create_notification(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
        )

        assert mock_logger.info.call_count >= 2

    # ---------------------------------------------------------
    # LOGGER ERROR CALLED
    # ---------------------------------------------------------

    @patch("notification.services.logger")
    @patch("notification.services.Notification.objects.create")
    def test_logger_error_called(
        self,
        mock_create,
        mock_logger,
        user,
    ):
        """
        Verify logger.error is executed on exception.
        """

        mock_create.side_effect = Exception("Database Error")

        with pytest.raises(Exception):

            NotificationService.create_notification(
                recipient=user,
                title="Welcome",
                message="Hello",
                notification_type="system",
            )

        mock_logger.error.assert_called_once()

    # ---------------------------------------------------------
    # CREATE CALLED WITH EXPECTED PARAMETERS
    # ---------------------------------------------------------

    @patch("notification.services.Notification.objects.create")
    def test_objects_create_called(
        self,
        mock_create,
        user,
    ):
        """
        Verify Notification.objects.create()
        receives correct parameters.
        """

        mock_notification = Notification(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
        )

        mock_create.return_value = mock_notification

        NotificationService.create_notification(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
        )

        mock_create.assert_called_once_with(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
            data={},
        )

    # ---------------------------------------------------------
    # CUSTOM NOTIFICATION TYPE
    # ---------------------------------------------------------

    def test_custom_notification_type(self, user):
        """
        Verify custom notification type is stored.
        """

        notification = NotificationService.create_notification(
            recipient=user,
            title="Interview",
            message="Interview Scheduled",
            notification_type="interview",
        )

        assert notification.notification_type == "interview"