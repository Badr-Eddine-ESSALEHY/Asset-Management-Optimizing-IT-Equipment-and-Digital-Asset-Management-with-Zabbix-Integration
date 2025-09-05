from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
import json
from datetime import datetime, timedelta

from assets.models import Equipment
from assets.services.zabbix_service import ZabbixIntegrationService, sync_equipment_to_zabbix, update_monitoring_data
from parcInfoCP import settings


def is_admin_or_technician(user):
    return user.is_staff or user.role in ['admin', 'technician']


@login_required
@user_passes_test(is_admin_or_technician)
def monitoring_dashboard(request):
    """Main monitoring dashboard"""
    # Get monitored equipment
    monitored_equipment = Equipment.objects.filter(
        monitoring_enabled=True,
        zabbix_hostid__isnull=False
    ).exclude(zabbix_hostid='').select_related('location', 'assigned_to')

    # Get equipment pending monitoring setup
    pending_equipment = Equipment.objects.filter(
        monitoring_enabled=True,
        ip_address__isnull=False
    ).filter(
        Q(zabbix_hostid__isnull=True) | Q(zabbix_hostid='')
    ).exclude(ip_address='')

    # Get monitoring statistics
    total_monitored = monitored_equipment.count()
    total_pending = pending_equipment.count()
    total_equipment = Equipment.objects.count()

    # Get recent monitoring alerts (from cache)
    recent_alerts = []
    for equipment in monitored_equipment[:10]:
        cache_key = f"monitoring_data_{equipment.id}"
        monitoring_data = cache.get(cache_key)
        if monitoring_data and monitoring_data.get('success'):
            triggers = monitoring_data.get('triggers', [])
            for trigger in triggers:
                if trigger.get('value') == '1':  # Problem state
                    recent_alerts.append({
                        'equipment': equipment,
                        'trigger': trigger,
                        'severity': trigger.get('priority', '0')
                    })

    # Sort alerts by severity
    recent_alerts.sort(key=lambda x: int(x['severity']), reverse=True)
    recent_alerts = recent_alerts[:20]  # Show only top 20

    context = {
        'monitored_equipment': monitored_equipment[:10],  # Show first 10
        'pending_equipment': pending_equipment,
        'total_monitored': total_monitored,
        'total_pending': total_pending,
        'total_equipment': total_equipment,
        'monitoring_coverage': round((total_monitored / max(total_equipment, 1)) * 100, 1),
        'recent_alerts': recent_alerts,
    }

    return render(request, 'assets/monitoring/dashboard.html', context)


@login_required
@user_passes_test(is_admin_or_technician)
def equipment_monitoring_detail(request, equipment_id):
    """Detailed monitoring view for specific equipment"""
    equipment = get_object_or_404(Equipment, id=equipment_id)

    # Check if user has permission to view this equipment
    if not request.user.is_staff and equipment.assigned_to != request.user:
        messages.error(request, "You don't have permission to view this equipment's monitoring data.")
        return redirect('monitoring_dashboard')

    monitoring_data = None
    if equipment.zabbix_hostid:
        # Try to get from cache first
        cache_key = f"monitoring_data_{equipment.id}"
        monitoring_data = cache.get(cache_key)

        if not monitoring_data:
            # Get fresh data from Zabbix
            service = ZabbixIntegrationService()
            monitoring_data = service.get_host_monitoring_data(equipment.zabbix_hostid, hours=48)
            if monitoring_data.get('success'):
                cache.set(cache_key, monitoring_data, timeout=300)

    # SNMP test result (if requested)
    snmp_test_result = None
    if request.GET.get('test_snmp') and equipment.ip_address:
        service = ZabbixIntegrationService()
        snmp_test_result = service.test_snmp_connectivity(equipment.ip_address)

    context = {
        'equipment': equipment,
        'monitoring_data': monitoring_data,
        'snmp_test_result': snmp_test_result,
        'can_manage': request.user.is_staff or request.user.role in ['admin', 'technician'],
    }

    return render(request, 'assets/monitoring/equipment_detail.html', context)


@login_required
@user_passes_test(is_admin_or_technician)
def sync_equipment_to_monitoring(request, equipment_id):
    """Sync specific equipment to Zabbix"""
    equipment = get_object_or_404(Equipment, id=equipment_id)

    if request.method == 'POST':
        # Trigger async sync
        sync_equipment_to_zabbix.delay(equipment_id)
        messages.success(request, f'Equipment "{equipment.name}" has been queued for Zabbix synchronization.')

    return redirect('equipment_monitoring_detail', equipment_id=equipment_id)


@login_required
@user_passes_test(is_admin_or_technician)
def bulk_sync_monitoring(request):
    """Bulk sync all equipment to Zabbix"""
    if request.method == 'POST':
        from assets.services.zabbix_service import bulk_sync_equipment
        bulk_sync_equipment.delay()
        messages.success(request, 'Bulk synchronization has been started. This may take several minutes.')

    return redirect('monitoring_dashboard')


@login_required
def api_monitoring_data(request, equipment_id):
    """API endpoint to get monitoring data for equipment"""
    equipment = get_object_or_404(Equipment, id=equipment_id)

    # Check permissions
    if not request.user.is_staff and equipment.assigned_to != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if not equipment.zabbix_hostid:
        return JsonResponse({'error': 'Equipment not monitored'}, status=404)

    # Get from cache
    cache_key = f"monitoring_data_{equipment.id}"
    monitoring_data = cache.get(cache_key)

    if not monitoring_data:
        return JsonResponse({'error': 'No monitoring data available'}, status=404)

    # Format data for frontend
    formatted_data = {
        'success': monitoring_data.get('success', False),
        'host_status': monitoring_data.get('host', {}).get('status', '1'),
        'items': [],
        'triggers': [],
        'charts': {}
    }

    if monitoring_data.get('success'):
        # Format items
        for item in monitoring_data.get('items', [])[:20]:
            formatted_data['items'].append({
                'name': item.get('name'),
                'value': item.get('lastvalue'),
                'units': item.get('units'),
                'last_check': datetime.fromtimestamp(int(item.get('lastclock', 0))).strftime(
                    '%Y-%m-%d %H:%M:%S') if item.get('lastclock') else 'Never'
            })

        # Format triggers
        for trigger in monitoring_data.get('triggers', []):
            severity_map = {'0': 'Not classified', '1': 'Information', '2': 'Warning', '3': 'Average', '4': 'High',
                            '5': 'Disaster'}
            formatted_data['triggers'].append({
                'description': trigger.get('description'),
                'status': 'Problem' if trigger.get('value') == '1' else 'OK',
                'severity': severity_map.get(trigger.get('priority', '0'), 'Unknown'),
                'priority': trigger.get('priority', '0')
            })

        # Format chart data for key metrics
        history = monitoring_data.get('history', {})
        for item_name, item_history in history.items():
            if len(item_history) > 1:
                chart_data = []
                for point in item_history[-50:]:  # Last 50 points
                    chart_data.append({
                        'timestamp': int(point.get('clock', 0)) * 1000,  # JavaScript timestamp
                        'value': float(point.get('value', 0)) if point.get('value', '').replace('.',
                                                                                                '').isdigit() else 0
                    })
                formatted_data['charts'][item_name] = chart_data

    return JsonResponse(formatted_data)


@login_required
@user_passes_test(is_admin_or_technician)
def monitoring_settings(request):
    """Monitoring configuration settings"""
    if request.method == 'POST':
        # Handle settings update
        action = request.POST.get('action')

        if action == 'test_connection':
            service = ZabbixIntegrationService()
            if service.api:
                messages.success(request, 'Zabbix API connection successful!')
            else:
                messages.error(request, 'Failed to connect to Zabbix API. Please check your settings.')

        elif action == 'refresh_monitoring':
            update_monitoring_data.delay()
            messages.success(request, 'Monitoring data refresh started.')

    # Get monitoring statistics
    service = ZabbixIntegrationService()
    connection_status = service.api is not None

    monitored_count = Equipment.objects.filter(
        monitoring_enabled=True,
        zabbix_hostid__isnull=False
    ).exclude(zabbix_hostid='').count()

    context = {
        'connection_status': connection_status,
        'monitored_count': monitored_count,
        'zabbix_config': settings.ZABBIX_CONFIG
    }

    return render(request, 'assets/monitoring/settings.html', context)