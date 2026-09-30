import logging
from asgiref.sync import sync_to_async
from django.shortcuts import render
from django.utils import timezone
from django.db import DatabaseError

from adrf.views import APIView

from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import Notification
from .serializers import NotificationSerializer, NotificationListSerializer

logger = logging.getLogger("notifications")

@sync_to_async
def get_serialized_data(serializer_class, queryset, many=False):
    """Instantiates a serializer and extracts its .data array safely in a sync thread."""
    return serializer_class(queryset, many=many).data

@sync_to_async
def get_single_serializer_data(serializer):
    """Extracts structural payload dictionaries from an instantiated serializer."""
    return serializer.data

def notification_page_view(request):
    return render(request, 'notification.html')

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    async def get(self, request):
        try:
            logger.info(f"[NotificationListView GET] Fetching notifications index for user={request.user.user_id}")

            queryset = Notification.objects.filter(recipient=request.user).order_by('is_read', '-created_at')

            serialized_data = await get_serialized_data(NotificationListSerializer, queryset, many=True)

            logger.info(f"[NotificationListView GET] Dataset parsed successfully for user={request.user.user_id}")
            return Response({
                "success": True,
                "data": serialized_data
            }, status=status.HTTP_200_OK)

        except DatabaseError as db_err:
            logger.error(f"[NotificationListView GET] Database connection exception: {str(db_err)}", exc_info=True)
            return Response({"success": False, "message": "Database error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception(f"[NotificationListView GET] Unexpected runtime failure: {str(e)}")
            return Response({"success": False, "message": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationUnreadCountView(APIView):
    """
    Standalone API endpoint dedicated exclusively to computing and returning 
    the unread notification balances for a specific user profile context.
    """
    permission_classes = [IsAuthenticated]

    async def get(self, request):
        try:
            logger.info(f"[NotificationUnreadCountView GET] Computing unread balance for user={request.user.user_id}")

            unread_count = await Notification.objects.filter(recipient=request.user, is_read=False).acount()

            logger.info(f"[NotificationUnreadCountView GET] Count verified. unread={unread_count}")
            return Response({
                'success': True,
                'unread_count': unread_count
            }, status=status.HTTP_200_OK)

        except DatabaseError as db_err:
            logger.error(f"[NotificationUnreadCountView GET] Core engine read failure: {str(db_err)}", exc_info=True)
            return Response({"success": False, "message": "Database error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception(f"[NotificationUnreadCountView GET] Unexpected exception context caught: {str(e)}")
            return Response({"success": False, "message": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    async def patch(self, request, pk):
        try:
            logger.info(f"[MarkNotificationReadView PATCH] Attempting state mutation on notification_id={pk} | user={request.user.user_id}")
            
            notification = await Notification.objects.aget(pk=pk, recipient=request.user)

            if not notification.is_read:
                logger.info(f"[MarkNotificationReadView PATCH] Item {pk} is unread. Modifying row entry metrics...")
                notification.is_read = True
                notification.read_at = timezone.now()
               
                await notification.asave(update_fields=["is_read", "read_at", "updated_at"])
                logger.info(f"[MarkNotificationReadView PATCH] Row committed cleanly to db storage for notification_id={pk}")
            else:
                logger.debug(f"[MarkNotificationReadView PATCH] Item {pk} was already read. Skipping state update pipeline.")

            serializer = NotificationSerializer(notification)
            serialized_payload = await get_single_serializer_data(serializer)

            return Response({
                "success": True,
                "notification": serialized_payload
            }, status=status.HTTP_200_OK)

        except Notification.DoesNotExist:
            logger.warning(f"[MarkNotificationReadView PATCH] Mismatch record lookups. Item ID={pk} target missing or access denied.")
            return Response(
                {"success": False, "error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as db_err:
            logger.error(f"[MarkNotificationReadView PATCH] Serialization transaction aborted due to database issue: {str(db_err)}", exc_info=True)
            return Response({"success": False, "message": "Database error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception(f"[MarkNotificationReadView PATCH] Critical failure mapping operation paths: {str(e)}")
            return Response({"success": False, "message": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)