import pytest
from django.urls import reverse
from django.core.cache import cache
from rest_framework.test import APIClient
from unittest.mock import patch
from Users.models import Users
from Users.views import hash_otp


# ================= FIXTURES =================

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user_data():
    return {
        "user_email": "test@example.com",
        "password": "Test@123",
        "confirm_password": "Test@123",
        "role": "jobseeker"
    }


@pytest.fixture
def urls():
    return {
        "register": reverse("register"),
        "verify": reverse("verify_email_otp"),
        "resend": reverse("resend_otp"),

        # ✅ Correct URLs from your urls.py
        "password_reset": reverse("change_password_request"),
        "confirm_password": reverse("password_change_otp"),
        "set_password": reverse("password_change"),

        "email_update": reverse("change_email_request"),
        "confirm_email": reverse("change_email_otp"),
        "set_email": reverse("change_email"),
    }


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# ================= REGISTER =================

@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_user_registration_success(mock_send, client, user_data, urls):
    res = client.post(urls["register"], user_data, format="json")

    assert res.status_code == 200
    assert "verify_token" in res.json()
    assert res.json()["message"] == "OTP sent to email"
    mock_send.assert_called_once()


@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_registration_rate_limit(mock_send, client, user_data, urls):
    for _ in range(11):  # limit = 10
        res = client.post(urls["register"], user_data, format="json")

    assert res.status_code in [403, 429]


@pytest.mark.django_db
def test_password_mismatch(client, user_data, urls):
    user_data["confirm_password"] = "wrong"

    res = client.post(urls["register"], user_data, format="json")

    assert res.status_code == 400


@pytest.mark.django_db
def test_duplicate_email(client, user_data, urls):
    Users.objects.create(
        user_email="test@example.com",
        password="hashed",
        is_active=True
    )

    res = client.post(urls["register"], user_data, format="json")

    assert res.status_code == 400


# ================= VERIFY OTP =================

@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_verify_otp_success(mock_send, client, user_data, urls):
    res = client.post(urls["register"], user_data, format="json")
    token = res.json()["verify_token"]
    email = user_data["user_email"]

    otp = "123456"

    cache.set(f"otp:register:{email}", hash_otp(otp), timeout=120)
    cache.set(f"register:{email}", user_data, timeout=300)

    res = client.post(urls["verify"], {
        "otp": otp,
        "verify_token": token
    }, format="json")

    assert res.status_code == 200
    assert Users.objects.filter(user_email=email).exists()


@pytest.mark.django_db
def test_missing_fields(client, urls):
    res = client.post(urls["verify"], {}, format="json")

    assert res.status_code == 400


@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_invalid_otp(mock_send, client, user_data, urls):
    res = client.post(urls["register"], user_data, format="json")
    token = res.json()["verify_token"]
    email = user_data["user_email"]

    cache.set(f"otp:register:{email}", hash_otp("123456"), timeout=120)
    cache.set(f"register:{email}", user_data, timeout=300)

    res = client.post(urls["verify"], {
        "otp": "000000",
        "verify_token": token
    }, format="json")

    assert res.status_code == 400


@pytest.mark.django_db
def test_expired_otp(client, user_data, urls):
    email = user_data["user_email"]

    cache.set(f"otp:register:{email}", hash_otp("123456"), timeout=1)
    cache.set(f"register:{email}", user_data, timeout=300)

    import time
    time.sleep(2)

    res = client.post(urls["verify"], {
        "otp": "123456",
        "verify_token": "fake"
    }, format="json")

    assert res.status_code == 400


@pytest.mark.django_db
def test_too_many_otp_attempts(client, user_data, urls):
    email = user_data["user_email"]
    token = "valid_token"

    cache.set(f"verify_token:{token}", email, timeout=300)
    cache.set(f"otp_attempt:{email}", 3, timeout=300)

    res = client.post(urls["verify"], {
        "otp": "123456",
        "verify_token": token
    }, format="json")

    assert res.status_code == 429


@pytest.mark.django_db
def test_token_attempt_limit(client, urls):
    token = "testtoken"
    ip = "127.0.0.1"

    cache.set(f"token_attempt:{token}:{ip}", 10, timeout=300)

    res = client.post(urls["verify"], {
        "otp": "123456",
        "verify_token": token
    }, format="json")

    assert res.status_code == 429


# ================= RESEND OTP =================

@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_resend_otp_success(mock_send, client, user_data, urls):
    res = client.post(urls["register"], user_data, format="json")
    token = res.json()["verify_token"]

    res = client.post(urls["resend"], {
        "verify_token": token
    }, format="json")

    assert res.status_code == 200
    assert mock_send.called


# ================= PASSWORD RESET =================

@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_request_password_reset_success(mock_send, client, urls):
    user = Users.objects.create(
        user_email="reset@test.com",
        password="hashed",
        is_active=True
    )

    res = client.post(urls["password_reset"], {
        "current_email": user.user_email
    }, format="json")

    assert res.status_code == 200
    assert "verify_token" in res.json()
    mock_send.assert_called_once()


@pytest.mark.django_db
def test_request_password_reset_user_not_found(client, urls):
    res = client.post(urls["password_reset"], {
        "current_email": "notfound@test.com"
    }, format="json")

    assert res.status_code == 404


@pytest.mark.django_db
def test_confirm_password_otp_success(client, urls):
    email = "reset@test.com"
    token = "valid_token"

    cache.set(f"verify_token:{token}", email, timeout=300)
    cache.set(f"otp:register:{email}", hash_otp("123456"), timeout=120)

    res = client.post(urls["confirm_password"], {
        "otp": "123456",
        "verify_token": token
    }, format="json")

    assert res.status_code == 200


@pytest.mark.django_db
def test_set_new_password_success(client, urls):
    user = Users.objects.create(
        user_email="reset@test.com",
        password="oldpass",
        is_active=True
    )

    token = "valid_token"
    email = user.user_email

    cache.set(f"verify_token:{token}", email, timeout=300)
    cache.set(f"reset_verified:{email}", True, timeout=300)

    res = client.post(urls["set_password"], {
        "verify_token": token,
        "password": "NewPass@123",
        "confirm_password": "NewPass@123"
    }, format="json")

    user.refresh_from_db()

    assert res.status_code == 200
    assert user.password != "oldpass"

@pytest.mark.django_db
def test_set_new_password_without_verification(client, urls):
    token = "token"

    cache.set(f"verify_token:{token}", "test@test.com", timeout=300)

    res = client.post(urls["set_password"], {
        "verify_token": token,
        "password": "NewPass@123"
    }, format="json")

    assert res.status_code == 400


# ================= EMAIL UPDATE =================

@patch("Users.views.send_otp_email_task.delay")
@pytest.mark.django_db
def test_request_email_update_success(mock_send, client, urls):
    user = Users.objects.create(
        user_email="old@test.com",
        password="pass",
        is_active=True
    )

    res = client.post(urls["email_update"], {
        "email": user.user_email
    }, format="json")

    assert res.status_code == 200
    assert "token" in res.json()
    mock_send.assert_called_once()


@pytest.mark.django_db
def test_confirm_email_otp_success(client, urls):
    token = "email_token"
    email = "old@test.com"

    cache.set(f"email_token:{token}", email, timeout=300)
    cache.set(f"otp:register:{email}", hash_otp("123456"), timeout=120)

    res = client.post(urls["confirm_email"], {
        "token": token,
        "otp": "123456"
    }, format="json")

    assert res.status_code == 200


@pytest.mark.django_db
def test_set_new_email_success(client, urls):
    user = Users.objects.create(
        user_email="old@test.com",
        password="pass",
        is_active=True
    )

    token = "email_token"

    cache.set(f"email_token:{token}", user.user_email, timeout=300)
    cache.set(f"email_verified:{token}", True, timeout=300)

    res = client.post(urls["set_email"], {
        "token": token,
        "new_email": "new@test.com"
    }, format="json")

    user.refresh_from_db()

    assert res.status_code == 200
    assert user.user_email == "new@test.com"


@pytest.mark.django_db
def test_set_new_email_already_exists(client, urls):
    Users.objects.create(user_email="new@test.com", password="pass")

    user = Users.objects.create(
        user_email="old@test.com",
        password="pass",
        is_active=True
    )

    token = "email_token"

    cache.set(f"email_token:{token}", user.user_email, timeout=300)
    cache.set(f"email_verified:{token}", True, timeout=300)

    res = client.post(urls["set_email"], {
        "token": token,
        "new_email": "new@test.com"
    }, format="json")

    assert res.status_code == 400


@pytest.mark.django_db
def test_set_new_email_same_as_old(client, urls):
    user = Users.objects.create(
        user_email="same@test.com",
        password="pass",
        is_active=True
    )

    token = "email_token"

    cache.set(f"email_token:{token}", user.user_email, timeout=300)
    cache.set(f"email_verified:{token}", True, timeout=300)

    res = client.post(urls["set_email"], {
        "token": token,
        "new_email": "same@test.com"
    }, format="json")

    assert res.status_code == 400


# ================= RATE LIMIT =================

@pytest.mark.django_db
def test_password_reset_rate_limit(client, urls):
    for _ in range(11):
        res = client.post(urls["password_reset"], {
            "current_email": "test@test.com"
        }, format="json")

    assert res.status_code in [403, 429]


@pytest.mark.django_db
def test_email_update_rate_limit(client, urls):
    for _ in range(11):
        res = client.post(urls["email_update"], {
            "email": "test@test.com"
        }, format="json")

    assert res.status_code in [403, 429]