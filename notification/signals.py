import logging
from asgiref.sync import async_to_sync
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from channels.layers import get_channel_layer
from .models import Notification

logger = logging.getLogger("notifications")

@receiver(pre_save, sender=Notification)
def notification_pre_save_handler(sender, instance, **kwargs):
    """
    Ensures structural tracking parameters are cleanly calculated
    before row updates or insertion states are written to disk.
    """
    logger.debug(f"[Signal PRE_SAVE] Evaluating notification state for user ID: {instance.recipient_id}")
    if instance.is_read and not instance.read_at:
        instance.read_at = timezone.now()
        logger.debug(f"[Signal PRE_SAVE] Assigned target read_at timestamp for notification: {instance.notification_id}")


@receiver(post_save, sender=Notification)
def notification_post_save_handler(sender, instance, created, **kwargs):
    """
    Fires instantly following successful row persistence blocks to broadcast 
    the serialization string directly over active real-time ASGI WebSocket slots.
    """
    if not created:
        return

    logger.info(f"[Signal POST_SAVE] Notification record created. Triggering live WebSocket broadcast. ID: {instance.notification_id}")

    try:
        channel_layer = get_channel_layer()
        # Define isolated unique channel room identifier targeting the user's stream
        user_group_name = f"user_notifications_{instance.recipient.user_id}"

        payload = {
            "type": "send_notification",
            "notification": {
                "notification_id": str(instance.notification_id),
                "title": instance.title,
                "message": instance.message,
                "notification_type": instance.notification_type,
                "is_read": instance.is_read,
                "time": "0 minutes ago"
            }
        }
        async_to_sync(channel_layer.group_send)(user_group_name, payload)
        logger.debug(f"[Signal POST_SAVE] Broadcast successfully multiplexed out to group track: {user_group_name}")

    except Exception as e:
        logger.error(f"[Signal POST_SAVE] Non-fatal WebSocket delivery disruption occurred: {str(e)}", exc_info=True)