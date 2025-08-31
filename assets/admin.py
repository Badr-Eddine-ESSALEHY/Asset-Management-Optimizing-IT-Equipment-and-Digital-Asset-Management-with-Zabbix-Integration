from django.contrib import admin
from .models import Location, Equipment, Software, License, Intervention


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor', 'room')
    search_fields = ('name', 'building')
    list_filter = ('is_active',)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'name', 'category', 'status', 'location', 'assigned_to')
    list_filter = ('category', 'status', 'location')
    search_fields = ('asset_tag', 'serial_number', 'name', 'ip_address')
    raw_id_fields = ('assigned_to', 'location')
    date_hierarchy = 'purchase_date'


@admin.register(Software)
class SoftwareAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'version', 'license_type')
    search_fields = ('name', 'vendor')
    list_filter = ('license_type', 'is_cloud')


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('software', 'license_key_short', 'status', 'expiration_date', 'assigned_to')
    list_filter = ('status', 'software')
    search_fields = ('license_key', 'software__name')
    raw_id_fields = ('assigned_to', 'installed_on')

    def license_key_short(self, obj):
        return f"{obj.license_key[:8]}..." if obj.license_key else ""

    license_key_short.short_description = "License Key"


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ('title', 'equipment', 'status', 'priority', 'scheduled_date')
    list_filter = ('status', 'priority')
    search_fields = ('title', 'equipment__name')
    date_hierarchy = 'scheduled_date'
    raw_id_fields = ('technician', 'equipment')