from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .models import Equipment
from .services.zabbix_service import ZabbixIntegrationService
import json


class MonitoringDashboardView(LoginRequiredMixin, ListView):
    """Main monitoring dashboard"""
    model = Equipment
    template_name = 'assets/monitoring_dashboard.html'
    context_object_name = 'equipment_list'

    def get_queryset(self):
        return Equipment.objects.filter(
            monitoring_enabled=True,
            zabbix_hostid__isnull=False
        ).select_related('location')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get monitoring statistics
        total_monitored = self.get_queryset().count()
        total_equipment = Equipment.objects.count()
        monitoring_enabled = Equipment.objects.filter(monitoring_enabled=True).count()

        context.update({
            'total_monitored': total_monitored,
            'total_equipment': total_equipment,
            'monitoring_enabled': monitoring_enabled,
            'monitoring_coverage': (monitoring_enabled / total_equipment * 100) if total_equipment > 0 else 0
        })

        return context


class EquipmentMonitoringDetailView(LoginRequiredMixin, DetailView):
    """Detailed monitoring view for specific equipment"""
    model = Equipment
    template_name = 'assets/equipment_monitoring_detail.html'
    context_object_name = 'equipment'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        equipment = self.get_object()

        if equipment.monitoring_enabled and equipment.zabbix_hostid:
            service = ZabbixIntegrationService()

            # Get monitoring data
            monitoring_result = service.get_host_data(equipment.zabbix_hostid)
            context['monitoring_data'] = monitoring_result.get('data') if monitoring_result['success'] else None
            context['monitoring_error'] = monitoring_result.get('error') if not monitoring_result['success'] else None

            # Test SNMP connectivity
            if equipment.ip_address:
                snmp_result = service.test_snmp_connectivity(str(equipment.ip_address))
                context['snmp_test'] = snmp_result

        return context


@login_required
def toggle_monitoring(request, pk):
    """Toggle monitoring for equipment"""
    equipment = get_object_or_404(Equipment, pk=pk)

    if request.method == 'POST':
        equipment.monitoring_enabled = not equipment.monitoring_enabled
        equipment.save()

        # Sync with Zabbix
        service = ZabbixIntegrationService()

        if equipment.monitoring_enabled and equipment.ip_address:
            if equipment.zabbix_hostid:
                result = service.update_host(equipment)
            else:
                result = service.create_host(equipment)
                if result['success']:
                    equipment.zabbix_hostid = result['hostid']
                    equipment.save()
        else:
            if equipment.zabbix_hostid:
                result = service.delete_host(equipment.zabbix_hostid)
                if result['success']:
                    equipment.zabbix_hostid = None
                    equipment.save()

        if 'result' in locals() and result['success']:
            status = "enabled" if equipment.monitoring_enabled else "disabled"
            messages.success(request, f"Monitoring {status} for {equipment.name}")
        elif 'result' in locals():
            messages.error(request, f"Error updating monitoring: {result['error']}")

    return redirect('assets:equipment_detail', pk=pk)


@login_required
def test_snmp_connection(request, pk):
    """Test SNMP connection for equipment"""
    equipment = get_object_or_404(Equipment, pk=pk)

    if not equipment.ip_address:
        return JsonResponse({
            'success': False,
            'error': 'Equipment must have an IP address'
        })

    service = ZabbixIntegrationService()
    result = service.test_snmp_connectivity(str(equipment.ip_address))

    return JsonResponse(result)


@login_required
def sync_equipment_monitoring(request, pk):
    """Manually sync equipment with Zabbix"""
    equipment = get_object_or_404(Equipment, pk=pk)

    if not equipment.monitoring_enabled:
        return JsonResponse({
            'success': False,
            'error': 'Monitoring is not enabled for this equipment'
        })

    if not equipment.ip_address:
        return JsonResponse({
            'success': False,
            'error': 'Equipment must have an IP address for monitoring'
        })

    service = ZabbixIntegrationService()

    if equipment.zabbix_hostid:
        result = service.update_host(equipment)
        action = "updated"
    else:
        result = service.create_host(equipment)
        if result['success']:
            equipment.zabbix_hostid = result['hostid']
            equipment.save()
        action = "created"

    if result['success']:
        result['message'] = f"Host {action} successfully"

    return JsonResponse(result)


@login_required
def monitoring_api_status(request):
    """Check Zabbix API connection status"""
    service = ZabbixIntegrationService()
    result = service.test_connection()
    return JsonResponse(result)