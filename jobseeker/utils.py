from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import sync_to_async

def custom_response(success, message, data=None, errors=None, status_code=status.HTTP_200_OK):
    return Response({
        "success": success,
        "message": message,
        "data": data,
        "errors": errors
    }, status=status_code)


@sync_to_async
def validate_serializer(serializer):
    """Safely runs serializer.is_valid() in a sync thread."""
    return serializer.is_valid()

@sync_to_async
def save_serializer(serializer, **kwargs):
    """Safely runs serializer.save() in a sync thread."""
    return serializer.save(**kwargs)

@sync_to_async
def get_serialized_data(serializer_class, *args, **kwargs):
    """Instantiates a serializer and returns its .data property safely."""
    return serializer_class(*args, **kwargs).data

@sync_to_async
def get_serializer_data_from_instance(serializer):
    """Safely extracts .data from an already instantiated serializer."""
    return serializer.data
