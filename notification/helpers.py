from notification.services import NotificationService
from notification.tasks import send_email_notification_task

def notify_user(
    recipient,
    title,
    message,
    notification_type='system',
    data=None,
    send_email=False
):

    notification = (
        NotificationService.create_notification(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data or {}
        )
    )

    if send_email:

        send_email_notification_task.delay(
            recipient_email=recipient.user_email,
            subject=title,
            message=message
        )

    return notification