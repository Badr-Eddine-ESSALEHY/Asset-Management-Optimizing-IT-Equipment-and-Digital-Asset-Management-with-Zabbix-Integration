# assets/urls.py

from django.urls import path
from . import views

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
]