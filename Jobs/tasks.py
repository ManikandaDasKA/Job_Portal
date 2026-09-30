import logging
from django.utils import timezone
from celery import shared_task
from celery.signals import worker_ready
from Jobs.models import Job

logger = logging.getLogger("jobs")

@shared_task
def auto_expire_deadline_jobs():
    """
    Periodic background task to find all OPEN jobs where the deadline has passed
    and change their status to EXPIRED.
    Runs synchronously as required by Celery workers using an efficient bulk update.
    """

    try:
        today = timezone.now().date()
        logger.info(f"[Scheduled Expiry] Executing job cleanup task for date: {today}")

        # Query all open jobs where deadline is less than today
        expired_jobs_queryset = Job.objects.filter(
            status=Job.Status.OPEN,
            deadline__lt=today,
        )

        # Get count for trace reporting
        count = expired_jobs_queryset.count()

        if count > 0:
            logger.info(f"[Scheduled Expiry] Found {count} open jobs past their deadline. Executing bulk update...")
            expired_jobs_queryset.update(status=Job.Status.EXPIRED)
            logger.info(f"[Scheduled Expiry] Success! Status set to EXPIRED for {count} job record(s).")
        
        else:
            logger.info("[Scheduled Expiry] Check finished: No jobs found requiring status expiration today.")

        return f"{count} jobs successfully transitioned to EXPIRED."

    except Exception as e:
        logger.exception(f"[Scheduled Expiry] Critical error encountered during database batch clean step: {str(e)}")
        raise

@worker_ready.connect
def run_on_startup(sender, **kwargs):
    """
    This signal hook triggers automatically the exact microsecond 
    the Celery worker restarts or comes live.
    """
    logger.info("[Celery Startup] Worker process is live! Triggering baseline job expiration sweep immediately...")
    
    # .delay() pushes the execution task context into the queue right now
    auto_expire_deadline_jobs.delay()