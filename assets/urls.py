# assets/urls.py

from django.urls import path
from . import views
from assets import zabbix_views, ai_views

app_name = 'assets'

urlpatterns = [
    # EQUIPMENT
    path('equipment/', views.EquipmentListView.as_view(), name='equipment_list'),
    path('equipment/add/', views.EquipmentCreateView.as_view(), name='equipment_add'),
    path('equipment/<int:pk>/', views.EquipmentDetailView.as_view(), name='equipment_detail'),
    path('equipment/<int:pk>/edit/', views.EquipmentUpdateView.as_view(), name='equipment_edit'),
    path('equipment/<int:pk>/delete/', views.EquipmentDeleteView.as_view(), name='equipment_delete'),

    # SOFTWARE
    path('software/', views.SoftwareListView.as_view(), name='software_list'),
    path('software/add/', views.SoftwareCreateView.as_view(), name='software_add'),
    path('software/<int:pk>/', views.SoftwareDetailView.as_view(), name='software_detail'),
    path('software/<int:pk>/edit/', views.SoftwareUpdateView.as_view(), name='software_edit'),
    path('software/<int:pk>/delete/', views.SoftwareDeleteView.as_view(), name='software_delete'),

    # LICENSES
    path('licenses/', views.LicenseListView.as_view(), name='license_list'),
    path('licenses/add/', views.LicenseCreateView.as_view(), name='license_add'),
    path('licenses/<int:pk>/', views.LicenseDetailView.as_view(), name='license_detail'),
    path('licenses/<int:pk>/edit/', views.LicenseUpdateView.as_view(), name='license_edit'),
    path('licenses/<int:pk>/delete/', views.LicenseDeleteView.as_view(), name='license_delete'),

    # INTERVENTIONS
    path('interventions/', views.InterventionListView.as_view(), name='intervention_list'),
    path('interventions/add/', views.InterventionCreateView.as_view(), name='intervention_add'),
    path('interventions/<int:pk>/', views.InterventionDetailView.as_view(), name='intervention_detail'),
    path('interventions/<int:pk>/edit/', views.InterventionUpdateView.as_view(), name='intervention_edit'),
    path('interventions/<int:pk>/delete/', views.InterventionDeleteView.as_view(), name='intervention_delete'),

    # MONITORING URLs
    path('monitoring/', zabbix_views.monitoring_dashboard, name='monitoring_dashboard'),
    path('monitoring/equipment/<int:equipment_id>/', zabbix_views.equipment_monitoring_detail,
         name='equipment_monitoring_detail'),
    path('monitoring/sync/<int:equipment_id>/', zabbix_views.sync_equipment_to_monitoring,
         name='sync_equipment_to_monitoring'),
    path('monitoring/bulk-sync/', zabbix_views.bulk_sync_monitoring, name='bulk_sync_monitoring'),
    path('monitoring/settings/', zabbix_views.monitoring_settings, name='monitoring_settings'),

    # AI URLs
    path('ai/', ai_views.ai_dashboard, name='ai_dashboard'),
    path('ai/predictive-maintenance/', ai_views.predictive_maintenance_view, name='predictive_maintenance'),
    path('ai/asset-categorization/', ai_views.asset_categorization_view, name='asset_categorization'),
    path('ai/image-recognition/', ai_views.image_recognition_view, name='image_recognition'),
    path('ai/equipment/<int:equipment_id>/analysis/', ai_views.equipment_ai_analysis, name='equipment_ai_analysis'),

    # AI API endpoints
    path('api/ai/health-analysis/', ai_views.api_run_health_analysis, name='api_run_health_analysis'),
    path('api/ai/health-analysis/<int:equipment_id>/', ai_views.api_run_health_analysis, name='api_run_health_analysis_equipment'),
    path('api/auto-categorize/', ai_views.api_auto_categorize, name='api_auto_categorize'),
    path('api/image-recognition/', ai_views.api_image_recognition, name='api_image_recognition'),
    path('api/unread-counts/', ai_views.api_unread_counts, name='api_unread_counts'),
    path('api/recent-messages/', ai_views.api_recent_messages, name='api_recent_messages'),

    # Monitoring API endpoints
    path('api/monitoring/<int:equipment_id>/', zabbix_views.api_monitoring_data, name='api_monitoring_data'),
]