from django.urls import path
from . import views

app_name = 'members'

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_member, name='login'),
    path('register/', views.register, name='register'),

    # Profile Management URLs
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('account-settings/', views.account_settings_view, name='account_settings'),

    # User Management URLs (Admin only)
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('toggle-user-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('bulk-user-actions/', views.bulk_user_actions, name='bulk_user_actions'),

    # Data Export URLs
    path('download-account-data/', views.download_account_data, name='download_account_data'),
    path('export-users/', views.export_users, name='export_users'),
    path('generate-report/', views.generate_report, name='generate_report'),

    # API Endpoints
    path('api/user-search/', views.user_search_api, name='user_search_api'),
    path('api/user-statistics/', views.user_statistics, name='user_statistics'),

    # Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]