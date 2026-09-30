# Inside notification/services.py
import logging
from .models import Notification

logger = logging.getLogger("notifications")

class NotificationService:

    @staticmethod
    def create_notification(recipient, title, message, notification_type='system', data=None):
        """
        Synchronous factory creation hook designed to explicitly maintain compatibility 
        with existing enterprise business logic wrappers while running signals internally.
        """
        logger.info(f"[NotificationService] Constructing tracking event record. Type: {notification_type} | User: {recipient.user_id}")
        try:
            # 1. Persist entry inside database (This automatically triggers the post_save signal!)
            notification = Notification.objects.create(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                data=data or {}
            )
            logger.info(f"[NotificationService] Row entry successfully saved. Generated UUID: {notification.notification_id}")

            return notification
            
        except Exception as e:
            logger.error(f"[NotificationService] Fatal storage execution drop during instantiation setup: {str(e)}", exc_info=True)
            raise