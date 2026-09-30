import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger("notifications")
User = get_user_model()

@shared_task(bind=True, max_retries=3)
def send_email_notification_task(self, recipient_email, subject, message):
    """
    Asynchronous network isolated delivery execution path handling 
    SMTP integrations safely on background Celery workers.
    """
    logger.info(f"[Celery Task] Attempting outbound email routing directly to destination: {recipient_email}")
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False
        )
        logger.info(f"[Celery Task] Mail routing verified successfully for target link: {recipient_email}")
        return f"Successfully dispatched notification email to {recipient_email}"
    except Exception as e:
        logger.error(f"[Celery Task] Network pipeline dropped packet delivery to {recipient_email}. Scheduling retries. Error: {str(e)}")
        raise self.retry(exc=e, countdown=10)

@shared_task
def notify_matching_users_task(job_id):
    """
    Background Task: Finds users whose skills match the newly created job's requirements
    and triggers a real-time notification to each of them without blocking the API response.
    """
    # Import locally inside the task to prevent circular imports during Celery worker boot
    from Jobs.models import Job
    from notification.services import NotificationService

    try:
        # 1. Fetch the job instance
        job = Job.objects.get(pk=job_id)

        # 2. Extract required skills/requirements
        # ⚠️ Change `job.skills.all()` to match your actual Job model's many-to-many field name!
        required_skills = job.skills.all() 
        
        if not required_skills.exists():
            logger.info(f"[Celery Worker] Job {job_id} has no skills listed. Skipping matches.")
            return "No skills required"

        # 3. Query active users who possess at least one of these matching skills.
        # ⚠️ Change `user_skills__in` to match your actual User/Profile model's skill field name!
        matching_users = User.objects.filter(
            user_skills__in=required_skills,
            is_active=True
        ).exclude(id=job.recruiter.id).distinct()

        matched_count = matching_users.count()
        logger.info(f"[Celery Worker] Found {matched_count} users matching skills for job '{job.title}'")

        # 4. Generate notifications (This automatically triggers your post_save signal and WebSocket push)
        for user in matching_users:
            NotificationService.create_notification(
                recipient=user,
                title="New Job Match! 🎉",
                message=f"A new role for '{job.title}' was just posted that matches your skills.",
                notification_type="job_match",
                data={
                    "job_id": str(job.job_id),
                    "title_slug": job.title_slug
                }
            )
            
        return f"Successfully notified {matched_count} matching users."

    except Job.DoesNotExist:
        logger.error(f"[Celery Worker] Job ID {job_id} not found. Cannot process matches.")
        return "Job not found"
    except Exception as e:
        logger.error(f"[Celery Worker] Error processing matches for job {job_id}: {str(e)}", exc_info=True)
        return "Task failed"