import pytest
from unittest.mock import MagicMock, patch

from django.utils import timezone

from notification.models import Notification
from notification.signals import (
    notification_pre_save_handler,
    notification_post_save_handler,
)


pytestmark = pytest.mark.django_db


class TestNotificationPreSaveSignal:

    # ---------------------------------------------------------
    # PRE SAVE - SET read_at
    # ---------------------------------------------------------

    def test_pre_save_sets_read_at(self, user):
        """
        If notification is marked as read and read_at is empty,
        signal should set read_at.
        """

        notification = Notification(
            recipient=user,
            title="Test",
            message="Message",
            notification_type="system",
            is_read=True,
            read_at=None,
        )

        notification_pre_save_handler(
            sender=Notification,
            instance=notification,
        )

        assert notification.read_at is not None

    # ---------------------------------------------------------
    # PRE SAVE - KEEP EXISTING read_at
    # ---------------------------------------------------------

    def test_pre_save_keeps_existing_read_at(self, user):
        """
        Existing read_at should not be modified.
        """

        current_time = timezone.now()

        notification = Notification(
            recipient=user,
            title="Test",
            message="Message",
            notification_type="system",
            is_read=True,
            read_at=current_time,
        )

        notification_pre_save_handler(
            sender=Notification,
            instance=notification,
        )

        assert notification.read_at == current_time

    # ---------------------------------------------------------
    # PRE SAVE - UNREAD NOTIFICATION
    # ---------------------------------------------------------

    def test_pre_save_unread_notification(self, user):
        """
        read_at should remain None
        for unread notifications.
        """

        notification = Notification(
            recipient=user,
            title="Test",
            message="Message",
            notification_type="system",
            is_read=False,
        )

        notification_pre_save_handler(
            sender=Notification,
            instance=notification,
        )

        assert notification.read_at is None


class TestNotificationPostSaveSignal:

    # ---------------------------------------------------------
    # POST SAVE SUCCESS
    # ---------------------------------------------------------

    @patch("notification.signals.async_to_sync")
    @patch("notification.signals.get_channel_layer")
    def test_post_save_broadcast(
        self,
        mock_get_channel_layer,
        mock_async_to_sync,
        user,
    ):
        """
        Verify websocket broadcast occurs.
        """

        channel_layer = MagicMock()
        mock_get_channel_layer.return_value = channel_layer

        group_send = MagicMock()

        mock_async_to_sync.return_value = group_send

        notification = Notification.objects.create(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
        )

        notification_post_save_handler(
            sender=Notification,
            instance=notification,
            created=True,
        )

        group_send.assert_called_once()

    # ---------------------------------------------------------
    # VERIFY PAYLOAD
    # ---------------------------------------------------------

    @patch("notification.signals.async_to_sync")
    @patch("notification.signals.get_channel_layer")
    def test_post_save_payload(
        self,
        mock_get_channel_layer,
        mock_async_to_sync,
        user,
    ):
        """
        Verify payload contains expected fields.
        """

        channel_layer = MagicMock()

        mock_get_channel_layer.return_value = channel_layer

        group_send = MagicMock()

        mock_async_to_sync.return_value = group_send

        notification = Notification.objects.create(
            recipient=user,
            title="Interview",
            message="Interview Scheduled",
            notification_type="interview",
        )

        notification_post_save_handler(
            sender=Notification,
            instance=notification,
            created=True,
        )

        args = group_send.call_args.args

        assert args[0] == f"user_notifications_{user.user_id}"

        payload = args[1]

        assert payload["type"] == "send_notification"
        assert payload["notification"]["title"] == "Interview"
        assert payload["notification"]["message"] == "Interview Scheduled"
        assert payload["notification"]["notification_type"] == "interview"

    # ---------------------------------------------------------
    # EXISTING NOTIFICATION (created=False)
    # ---------------------------------------------------------

    @patch("notification.signals.get_channel_layer")
    def test_post_save_existing_notification(
        self,
        mock_get_channel_layer,
        user,
    ):
        """
        group_send should never be called
        when created=False.
        """

        notification = Notification.objects.create(
            recipient=user,
            title="Test",
            message="Message",
            notification_type="system",
        )

        notification_post_save_handler(
            sender=Notification,
            instance=notification,
            created=False,
        )

        mock_get_channel_layer.assert_not_called()

    # ---------------------------------------------------------
    # CHANNEL LAYER EXCEPTION
    # ---------------------------------------------------------

    @patch("notification.signals.logger")
    @patch("notification.signals.get_channel_layer")
    def test_channel_layer_exception(
        self,
        mock_get_channel_layer,
        mock_logger,
        user,
    ):
        """
        Exception should be logged.
        """

        mock_get_channel_layer.side_effect = Exception("Redis Error")

        notification = Notification.objects.create(
            recipient=user,
            title="Test",
            message="Message",
            notification_type="system",
        )

        notification_post_save_handler(
            sender=Notification,
            instance=notification,
            created=True,
        )

        mock_logger.error.assert_called_once()

    # ---------------------------------------------------------
    # VERIFY async_to_sync CALLED
    # ---------------------------------------------------------

    @patch("notification.signals.async_to_sync")
    @patch("notification.signals.get_channel_layer")
    def test_async_to_sync_called(
        self,
        mock_get_channel_layer,
        mock_async_to_sync,
        user,
    ):
        """
        async_to_sync should wrap group_send.
        """

        channel_layer = MagicMock()

        mock_get_channel_layer.return_value = channel_layer

        notification = Notification.objects.create(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
        )

        notification_post_save_handler(
            sender=Notification,
            instance=notification,
            created=True,
        )

        mock_async_to_sync.assert_called_once_with(channel_layer.group_send)

    # ---------------------------------------------------------
    # LOGGER INFO
    # ---------------------------------------------------------

    @patch("notification.signals.logger")
    @patch("notification.signals.async_to_sync")
    @patch("notification.signals.get_channel_layer")
    def test_logger_info_called(
        self,
        mock_get_channel_layer,
        mock_async_to_sync,
        mock_logger,
        user,
    ):
        """
        Verify info logging.
        """

        channel_layer = MagicMock()

        mock_get_channel_layer.return_value = channel_layer

        mock_async_to_sync.return_value = MagicMock()

        notification = Notification.objects.create(
            recipient=user,
            title="Welcome",
            message="Hello",
            notification_type="system",
        )

        notification_post_save_handler(
            sender=Notification,
            instance=notification,
            created=True,
        )

        assert mock_logger.info.called