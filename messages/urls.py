# messages/urls.py

from django.urls import path
from . import views

app_name = 'messages'

urlpatterns = [
    # Main messaging views
    path('', views.messaging_dashboard, name='dashboard'),
    path('thread/<uuid:thread_id>/', views.thread_detail, name='thread_detail'),
    path('create/', views.create_thread, name='create_thread'),
    path('notifications/', views.system_notifications, name='notifications'),

    # Asset-related messaging
    path('intervention/<int:intervention_id>/', views.send_intervention_message, name='intervention_message'),
    path('equipment/<int:equipment_id>/', views.send_equipment_message, name='equipment_message'),

    # API endpoints
    path('api/users/search/', views.api_user_search, name='api_user_search'),
    path('api/thread/<uuid:thread_id>/messages/', views.api_thread_messages, name='api_thread_messages'),
    path('api/message/<uuid:message_id>/read/', views.api_mark_read, name='api_mark_read'),

    # Admin views
    path('admin/notifications/', views.admin_notifications, name='admin_notifications'),
    path('admin/notifications/create/', views.SystemNotificationCreateView.as_view(), name='create_notification'),
    path('api/notification/<uuid:notification_id>/read/', views.api_mark_notification_read,
         name='api_mark_notification_read'),
    path('api/notifications/mark-all-read/', views.api_mark_all_notifications_read,
         name='api_mark_all_notifications_read'),
]