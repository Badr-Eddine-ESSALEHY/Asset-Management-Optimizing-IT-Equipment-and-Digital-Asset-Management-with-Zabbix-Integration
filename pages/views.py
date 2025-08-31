from django.contrib.auth.decorators import login_required
from assets.models import Equipment, License, Software, Intervention
from django.shortcuts import render
from django.db.models import Count
from django.utils import timezone
import datetime
import json


def landing(request):
    return render(request, 'pages/landing.html')


@login_required
def dashboard(request):
    # Counts for summary cards
    total_equipment = Equipment.objects.count()
    total_licenses = License.objects.count()
    total_software = Software.objects.count()
    total_interventions = Intervention.objects.count()

    # Data for Ring Chart (Equipment, Licenses, Software, Interventions)
    ring_chart_data = {
        'Equipment': total_equipment,
        'Licenses': total_licenses,
        'Software': total_software,
        'Interventions': total_interventions
    }

    # Data for Intervention Status Line Chart
    intervention_status_qs = (
        Intervention.objects
        .values('status')
        .annotate(count=Count('status'))
    )
    intervention_status_data = {
        'Planned': 0,
        'In Progress': 0,
        'Completed': 0,
        'Cancelled': 0
    }

    # Map database values to display names
    status_mapping = {
        'planned': 'Planned',
        'in_progress': 'In Progress',
        'completed': 'Completed',
        'cancelled': 'Cancelled'
    }

    for item in intervention_status_qs:
        display_name = status_mapping.get(item['status'], item['status'].title())
        intervention_status_data[display_name] = item['count']

    # Equipment status breakdown for existing doughnut chart (keeping original)
    equipment_status_qs = (
        Equipment.objects
        .values('status')
        .annotate(count=Count('status'))
    )
    equipment_status_breakdown = {
        item['status']: item['count'] for item in equipment_status_qs
    }

    # Interventions over time for existing line chart (keeping original)
    today = timezone.now()
    start_date = today - datetime.timedelta(days=365)
    interventions_qs = (
        Intervention.objects
        .filter(scheduled_date__gte=start_date)
        .extra({'month': "strftime('%%Y-%%m', scheduled_date)"})
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    interventions_over_time = {
        item['month']: item['count'] for item in interventions_qs
    }

    # Populate missing months with 0
    months = [(start_date + datetime.timedelta(days=30 * i)).strftime('%Y-%m') for i in range(12)]
    for month in months:
        if month not in interventions_over_time:
            interventions_over_time[month] = 0

    # Recent items (optional)
    latest_equipment = Equipment.objects.order_by('-id')[:5]
    latest_licenses = License.objects.order_by('-id')[:5]
    latest_software = Software.objects.order_by('-id')[:5]
    latest_interventions = Intervention.objects.order_by('-id')[:5]

    context = {
        'total_equipment': total_equipment,
        'total_licenses': total_licenses,
        'total_software': total_software,
        'total_interventions': total_interventions,

        # New chart data
        'ring_chart_data': ring_chart_data,
        'intervention_status_data': intervention_status_data,

        # Existing chart data (keeping for compatibility)
        'equipment_status_breakdown': equipment_status_breakdown,
        'interventions_over_time': interventions_over_time,

        # Recent items
        'latest_equipment': latest_equipment,
        'latest_licenses': latest_licenses,
        'latest_software': latest_software,
        'latest_interventions': latest_interventions,
    }

    return render(request, 'pages/dashboard.html', context)