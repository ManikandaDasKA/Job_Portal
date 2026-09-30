from django.urls import path
from .views import NotificationListView, MarkNotificationReadView, NotificationUnreadCountView, notification_page_view

urlpatterns = [
    path('inbox/', notification_page_view, name='notification-page'),
    path('', NotificationListView.as_view(), name='notifications'),
    path('<uuid:pk>/read/', MarkNotificationReadView.as_view(), name='mark-read'),
    path('unread-count/', NotificationUnreadCountView.as_view(), name='unread-count'),
]