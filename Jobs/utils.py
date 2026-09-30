from Jobs.models import Category
from django.utils.text import slugify
from django.db import transaction
from asgiref.sync import sync_to_async

import logging

from rest_framework.pagination import PageNumberPagination

CACHE_TIMEOUT = 60 * 5

logger = logging.getLogger("jobs")

@sync_to_async
def validate_serializer(serializer):
    """Runs serializer validation in a background thread."""
    return serializer.is_valid()

@sync_to_async
def save_serializer(serializer, **kwargs):
    """Saves serializer instance data changes safely inside background threads."""
    return serializer.save(**kwargs)

@sync_to_async
def get_serializer_data(serializer):
    """Safely extracts dictionary representation payload structures from serializers."""
    return serializer.data

@sync_to_async
def paginate_queryset_async(paginator, queryset, request):
    """Executes legacy synchronous DRF pagination slicing operations safely inside threadpools."""
    return paginator.paginate_queryset(queryset, request)

class CategoryService:

    @staticmethod
    def get_or_create(name):

        try:

            normalized_name = name.strip().title()

            category = Category.objects.filter(
                name__iexact=normalized_name
            ).first()

            if category:

                logger.info(
                    f"Category already exists: "
                    f"{normalized_name}"
                )

                return category, False

            with transaction.atomic():

                category = Category.objects.create(
                    name=normalized_name,
                    slug=slugify(normalized_name)
                )

            logger.info(
                f"New category created: "
                f"{category.name}"
            )

            return category, True

        except Exception as e:

            logger.exception(
                f"CategoryService get_or_create failed: "
                f"{str(e)}"
            )

            raise
class CategoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50