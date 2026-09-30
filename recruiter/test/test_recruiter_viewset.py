import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from recruiter.models import Company, Recruiter
from Users.models import Users

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def company():
    owner = Users.objects.create_user(
        user_email="owner@testcompany.com",
        password="password"
    )
    return Company.objects.create(
        name="Test Company",
        domain="testcompany.com",
        created_by=owner,
        location="Kochi"
    )


@pytest.fixture
def user():
    return Users.objects.create_user(
        user_email="employee@testcompany.com",
        password="password"
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user)
    return api_client


class TestRecruiterCreate:

    def test_create_recruiter_success(self, auth_client, company):
        url = reverse("recruiter:recruiter-create")
        payload = {
            "company": company.company_id,
            "full_name": "John Doe",
            "designation": "Developer",
            "phone_number": "+1234567890",
            "gender": "male"
        }

        response = auth_client.post(url, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert Recruiter.objects.filter(user__user_email="employee@testcompany.com").exists()

    def test_duplicate_recruiter(self, auth_client, user, company):
        Recruiter.objects.create(
            user=user,
            company=company,
            full_name="John Doe",
            designation="Developer",
            phone_number="+1234567890"
        )

        url = reverse("recruiter:recruiter-create")
        # Ensure mandatory parameters are populated to safely trigger the duplicate filter check
        payload = {
            "company": company.company_id,
            "full_name": "John Doe",
            "designation": "Developer",
            "phone_number": "+1234567890",
            "gender": "male"
        }

        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRecruiterMe:

    def test_get_profile(self, auth_client, user, company):
        Recruiter.objects.create(
            user=user,
            company=company,
            have_access=True
        )

        url = reverse("recruiter:recruiter-me")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_profile_not_found(self, auth_client):
        url = reverse("recruiter:recruiter-me")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGiveAccess:

    def test_give_access_success(self, api_client):
        admin = Users.objects.create_user(
            user_email="admin@testcompany.com",
            password="password"
        )

        company = Company.objects.create(
            name="ABC Corp",
            domain="testcompany.com",
            created_by=admin,
            location="Kochi"
        )

        admin_rec = Recruiter.objects.create(
            user=admin,
            company=company,
            is_admin=True,
            have_access=True
        )

        employee = Users.objects.create_user(
            user_email="employee@testcompany.com",
            password="password"
        )

        Recruiter.objects.create(
            user=employee,
            company=company,
            have_access=False
        )

        api_client.force_authenticate(admin)

        # ✅ FIXED: Changed admin_rec.id to admin_rec.recruiter_id to align with model field rules
        url = reverse("recruiter:give-access", kwargs={"pk": admin_rec.recruiter_id})
        
        response = api_client.post(
            url,
            {"user_email": "employee@testcompany.com"}
        )

        assert response.status_code == status.HTTP_200_OK

        recruiter = Recruiter.objects.get(user=employee)
        assert recruiter.have_access is True