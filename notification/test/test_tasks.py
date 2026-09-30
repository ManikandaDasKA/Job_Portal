import pytest
from unittest.mock import patch

from notification.tasks import send_email_notification_task


pytestmark = pytest.mark.django_db


class TestSendEmailNotificationTask:

    # ---------------------------------------------------------
    # EMAIL SUCCESS
    # ---------------------------------------------------------

    @patch("notification.tasks.send_mail")
    def test_send_email_success(
        self,
        mock_send_mail,
        email_data,
        settings,
    ):
        """
        Verify email is sent successfully.
        """

        settings.DEFAULT_FROM_EMAIL = "noreply@test.com"

        mock_send_mail.return_value = 1

        result = send_email_notification_task.run(
            recipient_email=email_data["recipient_email"],
            subject=email_data["subject"],
            message=email_data["message"],
        )

        assert (
            result
            == f"Successfully dispatched notification email to {email_data['recipient_email']}"
        )

        mock_send_mail.assert_called_once_with(
            subject=email_data["subject"],
            message=email_data["message"],
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_data["recipient_email"]],
            fail_silently=False,
        )

    # ---------------------------------------------------------
    # EMAIL RETRY
    # ---------------------------------------------------------

    @patch("notification.tasks.send_mail")
    @patch.object(send_email_notification_task, "retry")
    def test_send_email_retry(
        self,
        mock_retry,
        mock_send_mail,
        email_data,
    ):
        """
        Verify retry() is called when send_mail fails.
        """

        exception = Exception("SMTP Connection Failed")

        mock_send_mail.side_effect = exception
        mock_retry.side_effect = Exception("Retry Triggered")

        with pytest.raises(Exception, match="Retry Triggered"):

            send_email_notification_task.run(
                recipient_email=email_data["recipient_email"],
                subject=email_data["subject"],
                message=email_data["message"],
            )

        mock_retry.assert_called_once()

    # ---------------------------------------------------------
    # LOGGER INFO
    # ---------------------------------------------------------

    @patch("notification.tasks.logger")
    @patch("notification.tasks.send_mail")
    def test_logger_info_called(
        self,
        mock_send_mail,
        mock_logger,
        email_data,
        settings,
    ):
        """
        Verify logger.info is called.
        """

        settings.DEFAULT_FROM_EMAIL = "noreply@test.com"

        mock_send_mail.return_value = 1

        send_email_notification_task.run(
            recipient_email=email_data["recipient_email"],
            subject=email_data["subject"],
            message=email_data["message"],
        )

        assert mock_logger.info.call_count == 2

    # ---------------------------------------------------------
    # LOGGER ERROR
    # ---------------------------------------------------------

    @patch("notification.tasks.logger")
    @patch.object(send_email_notification_task, "retry")
    @patch("notification.tasks.send_mail")
    def test_logger_error_called(
        self,
        mock_send_mail,
        mock_retry,
        mock_logger,
        email_data,
    ):
        """
        Verify logger.error is called when email sending fails.
        """

        exception = Exception("SMTP Error")

        mock_send_mail.side_effect = exception
        mock_retry.side_effect = Exception("Retry")

        with pytest.raises(Exception):

            send_email_notification_task.run(
                recipient_email=email_data["recipient_email"],
                subject=email_data["subject"],
                message=email_data["message"],
            )

        mock_logger.error.assert_called_once()

    # ---------------------------------------------------------
    # VERIFY SEND_MAIL ARGUMENTS
    # ---------------------------------------------------------

    @patch("notification.tasks.send_mail")
    def test_send_mail_called_with_expected_arguments(
        self,
        mock_send_mail,
        email_data,
        settings,
    ):
        """
        Verify send_mail receives correct parameters.
        """

        settings.DEFAULT_FROM_EMAIL = "admin@test.com"

        mock_send_mail.return_value = 1

        send_email_notification_task.run(
            recipient_email=email_data["recipient_email"],
            subject=email_data["subject"],
            message=email_data["message"],
        )

        args, kwargs = mock_send_mail.call_args

        assert kwargs["subject"] == email_data["subject"]
        assert kwargs["message"] == email_data["message"]
        assert kwargs["from_email"] == settings.DEFAULT_FROM_EMAIL
        assert kwargs["recipient_list"] == [email_data["recipient_email"]]
        assert kwargs["fail_silently"] is False

class TestNotifyMatchingUsersTask:

    # ---------------------------------------------------------
    # JOB DOES NOT EXIST
    # ---------------------------------------------------------

    @patch("notification.tasks.Job")
    @patch("notification.tasks.logger")
    def test_job_does_not_exist(
        self,
        mock_logger,
        mock_job,
    ):
        """
        Verify task returns 'Job not found'
        when the Job does not exist.
        """

        mock_job.objects.get.side_effect = mock_job.DoesNotExist

        result = notify_matching_users_task(job_id=1)

        assert result == "Job not found"

        mock_logger.error.assert_called_once()

    # ---------------------------------------------------------
    # NO REQUIRED SKILLS
    # ---------------------------------------------------------

    @patch("notification.tasks.Job")
    @patch("notification.tasks.logger")
    def test_no_required_skills(
        self,
        mock_logger,
        mock_job,
    ):
        """
        Verify task skips when the job
        has no required skills.
        """

        job = MagicMock()

        skills = MagicMock()
        skills.exists.return_value = False

        job.skills.all.return_value = skills

        mock_job.objects.get.return_value = job

        result = notify_matching_users_task(job_id=1)

        assert result == "No skills required"

        mock_logger.info.assert_called_once()

    # ---------------------------------------------------------
    # NO MATCHING USERS
    # ---------------------------------------------------------

    @patch("notification.tasks.NotificationService")
    @patch("notification.tasks.User")
    @patch("notification.tasks.Job")
    @patch("notification.tasks.logger")
    def test_no_matching_users(
        self,
        mock_logger,
        mock_job,
        mock_user,
        mock_notification_service,
    ):
        """
        Verify task completes successfully
        when no users match the required skills.
        """

        # Mock Job
        job = MagicMock()
        job.title = "Python Developer"

        recruiter = MagicMock()
        recruiter.id = 100

        job.recruiter = recruiter

        skills = MagicMock()
        skills.exists.return_value = True

        job.skills.all.return_value = skills

        mock_job.objects.get.return_value = job

        # Mock queryset chain
        queryset = MagicMock()

        queryset.exclude.return_value.distinct.return_value = []

        mock_user.objects.filter.return_value = queryset

        result = notify_matching_users_task(job_id=1)

        assert result == "Successfully notified 0 matching users."

        mock_notification_service.create_notification.assert_not_called()

        mock_logger.info.assert_called_once()

    # ---------------------------------------------------------
    # MATCHING USERS EXIST
    # ---------------------------------------------------------

    @patch("notification.services.NotificationService.create_notification")
    @patch("notification.tasks.User")
    @patch("Jobs.models.Job")
    def test_matching_users_exist(
        self,
        mock_job,
        mock_user,
        mock_create_notification,
    ):
        """
        Verify notifications are created
        for every matching user.
        """

        # Mock Job
        job = MagicMock()
        job.job_id = 1
        job.title = "Python Developer"
        job.title_slug = "python-developer"

        recruiter = MagicMock()
        recruiter.id = 100
        job.recruiter = recruiter

        # Mock skills
        skills = MagicMock()
        skills.exists.return_value = True

        job.skills.all.return_value = skills

        mock_job.objects.get.return_value = job

        # Mock users
        user1 = MagicMock()
        user2 = MagicMock()

        queryset = MagicMock()
        queryset.exclude.return_value.distinct.return_value = [
            user1,
            user2,
        ]

        mock_user.objects.filter.return_value = queryset

        result = notify_matching_users_task(job_id=1)

        assert result == "Successfully notified 2 matching users."

        assert mock_create_notification.call_count == 2

    # ---------------------------------------------------------
    # VERIFY create_notification PARAMETERS
    # ---------------------------------------------------------

    @patch("notification.services.NotificationService.create_notification")
    @patch("notification.tasks.User")
    @patch("Jobs.models.Job")
    def test_create_notification_called(
        self,
        mock_job,
        mock_user,
        mock_create_notification,
    ):
        """
        Verify NotificationService.create_notification()
        receives expected parameters.
        """

        job = MagicMock()
        job.job_id = 25
        job.title = "Backend Developer"
        job.title_slug = "backend-developer"

        recruiter = MagicMock()
        recruiter.id = 50
        job.recruiter = recruiter

        skills = MagicMock()
        skills.exists.return_value = True

        job.skills.all.return_value = skills

        mock_job.objects.get.return_value = job

        user = MagicMock()

        queryset = MagicMock()
        queryset.exclude.return_value.distinct.return_value = [user]

        mock_user.objects.filter.return_value = queryset

        notify_matching_users_task(job_id=25)

        mock_create_notification.assert_called_once_with(
            recipient=user,
            title="New Job Match! 🎉",
            message="A new role for 'Backend Developer' was just posted that matches your skills.",
            notification_type="job_match",
            data={
                "job_id": "25",
                "title_slug": "backend-developer",
            },
        )

    # ---------------------------------------------------------
    # GENERIC EXCEPTION
    # ---------------------------------------------------------

    @patch("Jobs.models.Job")
    @patch("notification.tasks.logger")
    def test_generic_exception(
        self,
        mock_logger,
        mock_job,
    ):
        """
        Verify generic exceptions are handled.
        """

        mock_job.objects.get.side_effect = Exception("Unexpected Error")

        result = notify_matching_users_task(job_id=1)

        assert result == "Task failed"

        mock_logger.error.assert_called_once()

    # ---------------------------------------------------------
    # LOGGER INFO
    # ---------------------------------------------------------

    @patch("notification.services.NotificationService.create_notification")
    @patch("notification.tasks.User")
    @patch("notification.tasks.logger")
    @patch("Jobs.models.Job")
    def test_logger_info(
        self,
        mock_job,
        mock_logger,
        mock_user,
        mock_create_notification,
    ):
        """
        Verify logger.info is called.
        """

        job = MagicMock()
        job.job_id = 1
        job.title = "Django Developer"
        job.title_slug = "django"

        recruiter = MagicMock()
        recruiter.id = 5

        job.recruiter = recruiter

        skills = MagicMock()
        skills.exists.return_value = True

        job.skills.all.return_value = skills

        mock_job.objects.get.return_value = job

        queryset = MagicMock()

        queryset.exclude.return_value.distinct.return_value = [
            MagicMock(),
        ]

        mock_user.objects.filter.return_value = queryset

        notify_matching_users_task(job_id=1)

        assert mock_logger.info.called

    # ---------------------------------------------------------
    # MULTIPLE USERS
    # ---------------------------------------------------------

    @patch("notification.services.NotificationService.create_notification")
    @patch("notification.tasks.User")
    @patch("Jobs.models.Job")
    def test_multiple_matching_users(
        self,
        mock_job,
        mock_user,
        mock_create_notification,
    ):
        """
        Verify every matched user receives a notification.
        """

        job = MagicMock()
        job.job_id = 11
        job.title = "Python Engineer"
        job.title_slug = "python-engineer"

        recruiter = MagicMock()
        recruiter.id = 20
        job.recruiter = recruiter

        skills = MagicMock()
        skills.exists.return_value = True

        job.skills.all.return_value = skills

        mock_job.objects.get.return_value = job

        users = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]

        queryset = MagicMock()

        queryset.exclude.return_value.distinct.return_value = users

        mock_user.objects.filter.return_value = queryset

        result = notify_matching_users_task(job_id=11)

        assert result == "Successfully notified 4 matching users."

        assert mock_create_notification.call_count == 4