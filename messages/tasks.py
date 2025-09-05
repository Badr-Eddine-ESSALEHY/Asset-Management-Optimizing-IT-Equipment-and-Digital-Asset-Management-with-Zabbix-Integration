from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.models import Q
from assets.models import Equipment, License, Intervention
from assets.predictive_maintenance import PredictiveMaintenanceService
from .models import SystemNotification
from .consumers import send_system_notification
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def check_license_expiration():
    """Check for licenses expiring soon and send notifications"""
    try:
        # Check licenses expiring in the next 30 days
        expiring_soon = License.objects.filter(
            expiration_date__lte=timezone.now().date() + timedelta(days=30),
            expiration_date__gt=timezone.now().date(),
            status='active'
        )

        for license in expiring_soon:
            days_remaining = (license.expiration_date - timezone.now().date()).days

            # Create notification
            notification = SystemNotification.objects.create(
                notification_type='license_expiring',
                title=f'License Expiring: {license.software.name}',
                message=f'The license for {license.software.name} will expire in {days_remaining} days on {license.expiration_date}.',
                target_roles='admin',
                related_license=license,
                action_url=f'/assets/licenses/{license.id}/',
                action_text='View License'
            )

            # Send real-time notification
            async_to_sync(send_system_notification)(
                'license_expiring',
                {
                    'license': {
                        'id': license.id,
                        'software_name': license.software.name,
                        'expiry_date': license.expiration_date.isoformat(),
                    },
                    'days_remaining': days_remaining
                },
                target_roles=['admin']
            )

        return f"Checked {expiring_soon.count()} expiring licenses"

    except Exception as e:
        logger.error(f"License expiration check failed: {e}")
        return f"Error: {e}"


@shared_task
def check_warranty_expiration():
    """Check for equipment warranties expiring soon"""
    try:
        expiring_soon = Equipment.objects.filter(
            warranty_expiration__lte=timezone.now().date() + timedelta(days=60),
            warranty_expiration__gt=timezone.now().date(),
            status__in=['available', 'assigned']
        )

        for equipment in expiring_soon:
            days_remaining = (equipment.warranty_expiration - timezone.now().date()).days

            notification = SystemNotification.objects.create(
                notification_type='warranty_expiring',
                title=f'Warranty Expiring: {equipment.name}',
                message=f'The warranty for {equipment.name} ({equipment.asset_tag}) expires in {days_remaining} days.',
                target_roles='admin',
                related_equipment=equipment,
                action_url=f'/assets/equipment/{equipment.id}/',
                action_text='View Equipment'
            )

            async_to_sync(send_system_notification)(
                'warranty_expiring',
                {
                    'equipment': {
                        'id': equipment.id,
                        'name': equipment.name,
                        'asset_tag': equipment.asset_tag,
                    },
                    'expiry_date': equipment.warranty_expiration.isoformat(),
                    'days_remaining': days_remaining
                },
                target_roles=['admin']
            )

        return f"Checked {expiring_soon.count()} expiring warranties"

    except Exception as e:
        logger.error(f"Warranty expiration check failed: {e}")
        return f"Error: {e}"


@shared_task
def check_maintenance_due():
    """Check for equipment that needs maintenance"""
    try:
        # Equipment with next_maintenance_date in the past or within 7 days
        maintenance_due = Equipment.objects.filter(
            Q(next_maintenance__lte=timezone.now().date() + timedelta(days=7)) &
            Q(next_maintenance__isnull=False),
            status__in=['available', 'assigned']
        )

        for equipment in maintenance_due:
            days_overdue = (timezone.now().date() - equipment.next_maintenance).days

            if days_overdue > 0:
                title = f'Maintenance Overdue: {equipment.name}'
                message = f'Maintenance for {equipment.name} ({equipment.asset_tag}) is {days_overdue} days overdue.'
                urgency = 'critical' if days_overdue > 14 else 'high'
            else:
                title = f'Maintenance Due: {equipment.name}'
                message = f'Maintenance for {equipment.name} ({equipment.asset_tag}) is due in {abs(days_overdue)} days.'
                urgency = 'normal'

            notification = SystemNotification.objects.create(
                notification_type='maintenance_due',
                title=title,
                message=message,
                target_roles='admin,technician',
                related_equipment=equipment,
                action_url=f'/assets/equipment/{equipment.id}/',
                action_text='Schedule Maintenance'
            )

        return f"Checked {maintenance_due.count()} equipment for maintenance"

    except Exception as e:
        logger.error(f"Maintenance check failed: {e}")
        return f"Error: {e}"


@shared_task
def run_predictive_maintenance():
    """Run predictive maintenance analysis on monitored equipment"""
    try:
        service = PredictiveMaintenanceService()

        # Get monitored equipment
        monitored_equipment = Equipment.objects.filter(
            monitoring_enabled=True,
            status__in=['available', 'assigned']
        ).exclude(zabbix_hostid__isnull=True)

        alerts_sent = 0

        for equipment in monitored_equipment:
            analysis = service.analyze_equipment_health(equipment.id, days=7)

            # Send alerts for high-risk equipment
            if analysis.get('risk_level') in ['high', 'critical']:
                notification = SystemNotification.objects.create(
                    notification_type='asset_alert',
                    title=f'Health Alert: {equipment.name}',
                    message=f'Predictive analysis indicates {analysis["risk_level"]} risk for {equipment.name}. Health score: {analysis.get("health_score", 0):.1f}/100.',
                    target_roles='admin,technician',
                    related_equipment=equipment,
                    action_url=f'/assets/equipment/{equipment.id}/',
                    action_text='View Details'
                )
                alerts_sent += 1

        return f"Analyzed {monitored_equipment.count()} equipment, sent {alerts_sent} alerts"

    except Exception as e:
        logger.error(f"Predictive maintenance task failed: {e}")
        return f"Error: {e}"


@shared_task
def cleanup_old_notifications():
    """Clean up old notifications to prevent database bloat"""
    try:
        # Delete notifications older than 90 days or explicitly expired
        cutoff_date = timezone.now() - timedelta(days=90)

        old_notifications = SystemNotification.objects.filter(
            Q(created_at__lt=cutoff_date) | Q(expires_at__lt=timezone.now())
        )

        count = old_notifications.count()
        old_notifications.delete()

        return f"Cleaned up {count} old notifications"

    except Exception as e:
        logger.error(f"Notification cleanup failed: {e}")
        return f"Error: {e}"


@shared_task
def send_daily_summary():
    """Send daily summary to admins"""
    try:
        # Get statistics for the day
        today = timezone.now().date()

        # Count various items
        new_interventions = Intervention.objects.filter(created_at__date=today).count()
        critical_equipment = Equipment.objects.filter(
            status='maintenance'
        ).count()
        expiring_licenses = License.objects.filter(
            expiration_date__lte=today + timedelta(days=30),
            expiration_date__gt=today
        ).count()

        if new_interventions > 0 or critical_equipment > 0 or expiring_licenses > 0:
            message = f"Daily Summary for {today}:\n"
            message += f"• New interventions: {new_interventions}\n"
            message += f"• Equipment in maintenance: {critical_equipment}\n"
            message += f"• Licenses expiring soon: {expiring_licenses}"

            notification = SystemNotification.objects.create(
                notification_type='system_update',
                title='Daily Asset Management Summary',
                message=message,
                target_roles='admin',
                action_url='/dashboard/',
                action_text='View Dashboard'
            )

        return f"Sent daily summary with {new_interventions} interventions, {critical_equipment} critical equipment"

    except Exception as e:
        logger.error(f"Daily summary task failed: {e}")
        return f"Error: {e}"