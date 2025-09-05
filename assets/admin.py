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


from django.contrib import admin
from django.utils.html import format_html
from assets.models import Equipment
from assets.services.zabbix_service import sync_equipment_to_zabbix


@admin.action(description='Sync selected equipment to Zabbix')
def sync_to_zabbix_action(modeladmin, request, queryset):
    """Admin action to sync equipment to Zabbix"""
    count = 0
    for equipment in queryset.filter(monitoring_enabled=True, ip_address__isnull=False):
        sync_equipment_to_zabbix.delay(equipment.id)
        count += 1

    modeladmin.message_user(
        request,
        f'{count} equipment items have been queued for Zabbix synchronization.'
    )


class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'asset_tag', 'category', 'status', 'monitoring_status', 'assigned_to', 'location']
    list_filter = ['category', 'status', 'monitoring_enabled', 'location']
    search_fields = ['name', 'asset_tag', 'serial_number', 'ip_address']
    actions = [sync_to_zabbix_action]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'asset_tag', 'serial_number', 'category', 'status')
        }),
        ('Hardware Details', {
            'fields': ('manufacturer', 'model', 'specifications', 'condition')
        }),
        ('Network Configuration', {
            'fields': ('hostname', 'ip_address', 'mac_address')
        }),
        ('Monitoring', {
            'fields': ('monitoring_enabled', 'zabbix_hostid'),
            'classes': ('collapse',)
        }),
        ('Assignment & Location', {
            'fields': ('assigned_to', 'assigned_date', 'location')
        }),
        ('Purchase & Maintenance', {
            'fields': ('purchase_date', 'warranty_expiration', 'purchase_cost',
                       'last_maintenance', 'next_maintenance')
        }),
        ('Additional Information', {
            'fields': ('notes', 'supplier', 'purchase_order'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['zabbix_hostid']

    def monitoring_status(self, obj):
        """Display monitoring status in admin"""
        if not obj.monitoring_enabled:
            return format_html('<span style="color: gray;">Disabled</span>')
        elif obj.zabbix_hostid:
            return format_html('<span style="color: green;">✓ Monitored</span>')
        elif obj.ip_address:
            return format_html('<span style="color: orange;">Pending Setup</span>')
        else:
            return format_html('<span style="color: red;">No IP Address</span>')

    monitoring_status.short_description = 'Monitoring'


# Re-register with new admin
admin.site.unregister(Equipment)
admin.site.register(Equipment, EquipmentAdmin)