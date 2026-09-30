import json
import logging
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from notification.consumers import NotificationConsumer

pytestmark = pytest.mark.asyncio


class TestNotificationConsumerMethods:

    # ---------------------------------------------------------
    # disconnect()
    # ---------------------------------------------------------

    async def test_disconnect(self):
        """
        Verify heartbeat task is cancelled and the channel group
        is discarded on disconnect.
        """

        consumer = NotificationConsumer()

        consumer.user_group_name = "user_notifications_1"
        consumer.channel_name = "test-channel"

        consumer.channel_layer = MagicMock()
        consumer.channel_layer.group_discard = AsyncMock()

        heartbeat = MagicMock()
        heartbeat.cancel = MagicMock()

        consumer.heartbeat_task = heartbeat

        await consumer.disconnect(1000)

        heartbeat.cancel.assert_called_once()

        consumer.channel_layer.group_discard.assert_awaited_once_with(
            "user_notifications_1",
            "test-channel",
        )

    # ---------------------------------------------------------
    # receive() with pong
    # ---------------------------------------------------------

    async def test_receive_pong(self):
        """
        Consumer should accept a pong message
        without raising an exception.
        """

        consumer = NotificationConsumer()

        payload = json.dumps({
            "type": "pong"
        })

        # Should execute successfully
        await consumer.receive(payload)

    # ---------------------------------------------------------
    # receive() invalid JSON
    # ---------------------------------------------------------

    async def test_receive_invalid_json(self):
        """
        Invalid JSON should be ignored gracefully.
        """

        consumer = NotificationConsumer()

        await consumer.receive("invalid-json")

    # ---------------------------------------------------------
    # send_notification()
    # ---------------------------------------------------------

    async def test_send_notification(self):
        """
        Verify notification payload is sent to the websocket.
        """

        consumer = NotificationConsumer()

        consumer.send = AsyncMock()

        event = {
            "notification": {
                "notification_id": "123",
                "title": "Job Alert",
                "message": "Python Developer",
                "notification_type": "job_alert",
                "is_read": False,
                "time": "Just now",
            }
        }

        await consumer.send_notification(event)

        consumer.send.assert_awaited_once_with(
            text_data=json.dumps({
                "success": True,
                "data": event["notification"]
            })
        )

    # ---------------------------------------------------------
    # disconnect() without heartbeat
    # ---------------------------------------------------------

    async def test_disconnect_without_heartbeat(self):
        """
        Consumer should disconnect cleanly even if
        heartbeat task was never created.
        """

        consumer = NotificationConsumer()

        consumer.user_group_name = "user_notifications_1"
        consumer.channel_name = "test-channel"

        consumer.channel_layer = MagicMock()
        consumer.channel_layer.group_discard = AsyncMock()

        consumer.heartbeat_task = None

        await consumer.disconnect(1000)

        consumer.channel_layer.group_discard.assert_awaited_once()

    # ---------------------------------------------------------
    # receive() with unknown message
    # ---------------------------------------------------------

    async def test_receive_unknown_message(self):
        """
        Unknown websocket messages should be ignored.
        """

        consumer = NotificationConsumer()

        payload = json.dumps({
            "type": "unknown",
            "message": "Hello"
        })

        await consumer.receive(payload)


class TestNotificationConsumerHeartbeat:

    # ---------------------------------------------------------
    # Heartbeat sends ping
    # ---------------------------------------------------------

    @patch("notification.consumer.asyncio.sleep", new_callable=AsyncMock)
    async def test_send_heartbeat_loop(
        self,
        mock_sleep,
    ):
        """
        Verify heartbeat sends ping.
        Stop loop after first iteration.
        """

        consumer = NotificationConsumer()

        consumer.user = MagicMock()
        consumer.user.user_id = "USR001"

        consumer.send = AsyncMock()

        async def sleep_side_effect(*args, **kwargs):
            raise asyncio.CancelledError()

        mock_sleep.side_effect = sleep_side_effect

        await consumer.send_heartbeat_loop()

        consumer.send.assert_awaited_once_with(
            text_data=json.dumps({"type": "ping"})
        )

    # ---------------------------------------------------------
    # CancelledError handled correctly
    # ---------------------------------------------------------

    @patch("notification.consumer.asyncio.sleep", new_callable=AsyncMock)
    async def test_heartbeat_cancelled(
        self,
        mock_sleep,
    ):
        """
        Verify CancelledError exits gracefully.
        """

        consumer = NotificationConsumer()

        consumer.user = MagicMock()
        consumer.user.user_id = "USR001"

        consumer.send = AsyncMock()

        mock_sleep.side_effect = asyncio.CancelledError()

        # Should not raise
        await consumer.send_heartbeat_loop()

    # ---------------------------------------------------------
    # Multiple heartbeat iterations
    # ---------------------------------------------------------

    @patch("notification.consumer.asyncio.sleep", new_callable=AsyncMock)
    async def test_multiple_heartbeat_iterations(
        self,
        mock_sleep,
    ):
        """
        Simulate three heartbeat cycles.
        """

        consumer = NotificationConsumer()

        consumer.user = MagicMock()
        consumer.user.user_id = "USR001"

        consumer.send = AsyncMock()

        counter = 0

        async def sleep_side_effect(*args, **kwargs):
            nonlocal counter
            counter += 1

            if counter >= 3:
                raise asyncio.CancelledError()

        mock_sleep.side_effect = sleep_side_effect

        await consumer.send_heartbeat_loop()

        assert consumer.send.await_count == 3

    # ---------------------------------------------------------
    # Verify ping payload
    # ---------------------------------------------------------

    @patch("notification.consumer.asyncio.sleep", new_callable=AsyncMock)
    async def test_ping_payload(
        self,
        mock_sleep,
    ):
        """
        Verify correct ping payload.
        """

        consumer = NotificationConsumer()

        consumer.user = MagicMock()
        consumer.user.user_id = "USR001"

        consumer.send = AsyncMock()

        async def stop_loop(*args, **kwargs):
            raise asyncio.CancelledError()

        mock_sleep.side_effect = stop_loop

        await consumer.send_heartbeat_loop()

        args = consumer.send.await_args.kwargs

        payload = json.loads(args["text_data"])

        assert payload["type"] == "ping"

    # ---------------------------------------------------------
    # Disconnect without user_group_name
    # ---------------------------------------------------------

    async def test_disconnect_without_group(self):
        """
        Should not fail when user_group_name
        doesn't exist.
        """

        consumer = NotificationConsumer()

        consumer.channel_layer = MagicMock()
        consumer.channel_layer.group_discard = AsyncMock()

        consumer.heartbeat_task = None

        # user_group_name intentionally absent

        await consumer.disconnect(1000)

        consumer.channel_layer.group_discard.assert_not_called()

    # ---------------------------------------------------------
    # Missing user object
    # ---------------------------------------------------------

    @patch("notification.consumer.asyncio.sleep", new_callable=AsyncMock)
    async def test_missing_user_attribute(
        self,
        mock_sleep,
    ):
        """
        Edge case where consumer.user
        is unexpectedly missing.
        """

        consumer = NotificationConsumer()

        consumer.send = AsyncMock()

        async def stop_loop(*args, **kwargs):
            raise asyncio.CancelledError()

        mock_sleep.side_effect = stop_loop

        with pytest.raises(AttributeError):
            await consumer.send_heartbeat_loop()