# tests/test_views.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from django.db import DatabaseError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

# ✅ FIXED: Imported the Notification model to resolve NameError on line 339
from notification.models import Notification

pytestmark = pytest.mark.django_db


class TestNotificationListView:

    @pytest.fixture
    def url(self):
        return reverse("notification:notification-list")

    @pytest.fixture
    def client(self):
        return APIClient()

    # ------------------------------------------------------------------
    # SUCCESS
    # ------------------------------------------------------------------

    @patch("notification.views.get_serialized_data", new_callable=AsyncMock)
    def test_get_notifications_success(
        self,
        mock_serializer,
        auth_client,
        user,
        notification,
        url,
    ):
        mock_serializer.return_value = [
            {
                "notification_id": str(notification.notification_id),
                "message": notification.message,
                "time": "1 minute ago",
            }
        ]

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert len(response.data["data"]) == 1

        mock_serializer.assert_awaited_once()

    # ------------------------------------------------------------------
    # EMPTY LIST
    # ------------------------------------------------------------------

    @patch("notification.views.get_serialized_data", new_callable=AsyncMock)
    def test_empty_notification_list(
        self,
        mock_serializer,
        auth_client,
        empty_notifications,
        url,
    ):
        mock_serializer.return_value = []

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["data"] == []

    # ------------------------------------------------------------------
    # UNAUTHORIZED
    # ------------------------------------------------------------------

    def test_unauthorized_user(
        self,
        client,
        url,
    ):
        response = client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ------------------------------------------------------------------
    # DATABASE ERROR
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.filter")
    def test_database_error(
        self,
        mock_filter,
        auth_client,
        url,
    ):
        mock_filter.side_effect = DatabaseError("Database Failure")

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Database error"

    # ------------------------------------------------------------------
    # GENERIC EXCEPTION
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.filter")
    def test_generic_exception(
        self,
        mock_filter,
        auth_client,
        url,
    ):
        mock_filter.side_effect = Exception("Unexpected Error")

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Internal server error"

    # ------------------------------------------------------------------
    # SERIALIZER EXCEPTION
    # ------------------------------------------------------------------

    @patch("notification.views.get_serialized_data", new_callable=AsyncMock)
    def test_serializer_exception(
        self,
        mock_serializer,
        auth_client,
        notification,
        url,
    ):
        mock_serializer.side_effect = Exception("Serializer Failed")

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Internal server error"


class TestNotificationUnreadCountView:

    @pytest.fixture
    def url(self):
        return reverse("notification:notification-unread-count")

    @pytest.fixture
    def client(self):
        return APIClient()

    # ------------------------------------------------------------------
    # SUCCESS
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.filter")
    async def test_unread_count_success(
        self,
        mock_filter,
        auth_client,
        user,
        url,
    ):
        mock_queryset = MagicMock()
        mock_queryset.acount = AsyncMock(return_value=5)

        mock_filter.return_value = mock_queryset

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["unread_count"] == 5

        mock_queryset.acount.assert_awaited_once()

    # ------------------------------------------------------------------
    # ZERO UNREAD
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.filter")
    async def test_zero_unread_notifications(
        self,
        mock_filter,
        auth_client,
        url,
    ):
        mock_queryset = MagicMock()
        mock_queryset.acount = AsyncMock(return_value=0)

        mock_filter.return_value = mock_queryset

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert response.data["unread_count"] == 0

    # ------------------------------------------------------------------
    # UNAUTHORIZED
    # ------------------------------------------------------------------

    def test_unauthorized_user(
        self,
        client,
        url,
    ):
        response = client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ------------------------------------------------------------------
    # DATABASE ERROR
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.filter")
    def test_database_error(
        self,
        mock_filter,
        auth_client,
        url,
    ):
        mock_filter.side_effect = DatabaseError("Database Failure")

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Database error"

    # ------------------------------------------------------------------
    # GENERIC EXCEPTION
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.filter")
    def test_generic_exception(
        self,
        mock_filter,
        auth_client,
        url,
    ):
        mock_filter.side_effect = Exception("Unexpected Error")

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Internal server error"


class TestMarkNotificationReadView:

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self, notification):
        return reverse(
            "notification:notification-mark-read",
            kwargs={"pk": notification.notification_id},
        )

    # ------------------------------------------------------------------
    # SUCCESS
    # ------------------------------------------------------------------

    @patch("notification.views.get_single_serializer_data", new_callable=AsyncMock)
    async def test_mark_notification_read_success(
        self,
        mock_serializer,
        auth_client,
        notification,
        url,
    ):
        mock_serializer.return_value = {
            "notification_id": str(notification.notification_id),
            "title": notification.title,
            "message": notification.message,
            "is_read": True,
        }

        response = auth_client.patch(url)

        notification.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert notification.is_read is True
        assert notification.read_at is not None

        mock_serializer.assert_awaited_once()

    # ------------------------------------------------------------------
    # ALREADY READ
    # ------------------------------------------------------------------

    @patch("notification.views.get_single_serializer_data", new_callable=AsyncMock)
    async def test_notification_already_read(
        self,
        mock_serializer,
        auth_client,
        read_notification,
    ):
        url = reverse(
            "notification:notification-mark-read",
            kwargs={"pk": read_notification.notification_id},
        )

        mock_serializer.return_value = {
            "notification_id": str(read_notification.notification_id),
            "is_read": True,
        }

        response = auth_client.patch(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True

        read_notification.refresh_from_db()

        assert read_notification.is_read is True

    # ------------------------------------------------------------------
    # NOT FOUND
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.aget", new_callable=AsyncMock)
    async def test_notification_not_found(
        self,
        mock_aget,
        auth_client,
    ):
        mock_aget.side_effect = Notification.DoesNotExist

        url = reverse(
            "notification:notification-mark-read",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )

        response = auth_client.patch(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["success"] is False
        assert response.data["error"] == "Notification not found"

    # ------------------------------------------------------------------
    # UNAUTHORIZED
    # ------------------------------------------------------------------

    def test_unauthorized_user(
        self,
        client,
        notification,
    ):
        url = reverse(
            "notification:notification-mark-read",
            kwargs={"pk": notification.notification_id},
        )

        response = client.patch(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ------------------------------------------------------------------
    # DATABASE ERROR
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.aget", new_callable=AsyncMock)
    async def test_database_error(
        self,
        mock_aget,
        auth_client,
        notification,
    ):
        mock_aget.side_effect = DatabaseError("Database Failure")

        url = reverse(
            "notification:notification-mark-read",
            kwargs={"pk": notification.notification_id},
        )

        response = auth_client.patch(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Database error"

    # ------------------------------------------------------------------
    # GENERIC EXCEPTION
    # ------------------------------------------------------------------

    @patch("notification.views.Notification.objects.aget", new_callable=AsyncMock)
    async def test_generic_exception(
        self,
        mock_aget,
        auth_client,
        notification,
    ):
        mock_aget.side_effect = Exception("Unexpected Error")

        url = reverse(
            "notification:notification-mark-read",
            kwargs={"pk": notification.notification_id},
        )

        response = auth_client.patch(url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["success"] is False
        assert response.data["message"] == "Internal server error"