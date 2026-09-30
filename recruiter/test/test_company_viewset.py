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
def user():
    return Users.objects.create_user(
        user_email="admin@testcompany.com",
        password="password123"
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def company(user):
    return Company.objects.create(
        name="Test Company",
        domain="testcompany.com",
        created_by=user,
        is_verified=False
    )


@pytest.fixture
def admin_recruiter(user, company):
    return Recruiter.objects.create(
        user=user,
        company=company,
        is_admin=True,
        have_access=True
    )


class TestCompanyCreate:

    def test_create_company_success(self, auth_client, user):
        user.user_email = "operator@abctechnologies.com"
        user.save()

        url = reverse("recruiter:company-list")
        payload = {
            "name": "ABC Technologies",
            "description": "Software Company",
            "website": "https://abc.com",
            "location": "Kochi",
            "industry": "IT"
        }

        response = auth_client.post(url, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert Company.objects.filter(name="ABC Technologies").exists()

    def test_duplicate_company_name(self, auth_client, company):
        url = reverse("recruiter:company-list")
        payload = {
            "name": company.name,
            "description": "Software",
            "website": "https://new.com",
            "location": "Kochi",
            "industry": "IT"
        }

        response = auth_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_email(self, api_client):
        invalid_user = Users.objects.create_user(
            user_email="invalidemail",
            password="password"
        )
        api_client.force_authenticate(invalid_user)

        url = reverse("recruiter:company-list")
        payload = {
            "name": "XYZ",
            "location": "Kochi"
        }

        response = api_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCompanyUpdate:

    def test_update_company_by_admin(self, auth_client, company, admin_recruiter):
        url = reverse("recruiter:company-detail", kwargs={"pk": company.company_id})
        payload = {"name": "Updated Company"}

        response = auth_client.patch(url, payload)

        assert response.status_code == status.HTTP_200_OK
        company.refresh_from_db()
        assert company.name == "Updated Company"

    def test_update_company_without_admin(self, api_client, company):
        non_admin_user = Users.objects.create_user(
            user_email="employee@testcompany.com",
            password="password"
        )
        Recruiter.objects.create(
            user=non_admin_user,
            company=company,
            is_admin=False,
            have_access=True
        )
        api_client.force_authenticate(non_admin_user)

        url = reverse("recruiter:company-detail", kwargs={"pk": company.company_id})
        response = api_client.patch(url, {"name": "New Name"})

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCompanyDelete:

    def test_delete_company(self, auth_client, company, admin_recruiter):
        url = reverse("recruiter:company-detail", kwargs={"pk": company.company_id})
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert Company.objects.count() == 0