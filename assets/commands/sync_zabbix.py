from django.core.management.base import BaseCommand
from django.db import transaction
from assets.models import Equipment
from assets.services.zabbix_service import ZabbixIntegrationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Synchronize Equipment with Zabbix monitoring system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Test connection to Zabbix API',
        )
        parser.add_argument(
            '--bulk',
            action='store_true',
            help='Sync all monitoring-enabled equipment',
        )
        parser.add_argument(
            '--equipment-id',
            type=int,
            help='Sync specific equipment by ID',
        )
        parser.add_argument(
            '--update-data',
            action='store_true',
            help='Update monitoring data for existing hosts',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Remove disabled equipment from Zabbix',
        )

    def handle(self, *args, **options):
        service = ZabbixIntegrationService()

        if options['test_connection']:
            self.test_connection(service)
        elif options['bulk']:
            self.bulk_sync(service)
        elif options['equipment_id']:
            self.sync_single_equipment(service, options['equipment_id'])
        elif options['update_data']:
            self.update_monitoring_data(service)
        elif options['cleanup']:
            self.cleanup_disabled_equipment(service)
        else:
            self.stdout.write(
                self.style.WARNING('Please specify an action. Use --help for options.')
            )

    def test_connection(self, service):
        """Test Zabbix API connection"""
        self.stdout.write("Testing Zabbix API connection...")
        result = service.test_connection()

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ {result['message']}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Connection failed: {result['error']}")
            )

    def bulk_sync(self, service):
        """Sync all monitoring-enabled equipment"""
        self.stdout.write("Starting bulk synchronization...")

        # Get equipment that should be monitored
        equipment_to_monitor = Equipment.objects.filter(
            monitoring_enabled=True,
            ip_address__isnull=False
        ).exclude(ip_address='')

        success_count = 0
        error_count = 0

        for equipment in equipment_to_monitor:
            try:
                with transaction.atomic():
                    if equipment.zabbix_hostid:
                        result = service.update_host(equipment)
                        action = "Updated"
                    else:
                        result = service.create_host(equipment)
                        if result['success']:
                            equipment.zabbix_hostid = result['hostid']
                            equipment.save()
                        action = "Created"

                    if result['success']:
                        self.stdout.write(f"✅ {action} host for {equipment.name}")
                        success_count += 1
                    else:
                        self.stdout.write(f"❌ Failed to {action.lower()} {equipment.name}: {result['error']}")
                        error_count += 1

            except Exception as e:
                self.stdout.write(f"❌ Error processing {equipment.name}: {e}")
                error_count += 1

        # Clean up disabled equipment
        disabled_equipment = Equipment.objects.filter(
            monitoring_enabled=False,
            zabbix_hostid__isnull=False
        )

        for equipment in disabled_equipment:
            try:
                result = service.delete_host(equipment.zabbix_hostid)
                if result['success']:
                    equipment.zabbix_hostid = None
                    equipment.save()
                    self.stdout.write(f"🗑️ Removed {equipment.name} from monitoring")
                    success_count += 1
            except Exception as e:
                self.stdout.write(f"❌ Error removing {equipment.name}: {e}")
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nBulk sync completed: {success_count} successful, {error_count} errors")
        )

    def sync_single_equipment(self, service, equipment_id):
        """Sync a single piece of equipment"""
        try:
            equipment = Equipment.objects.get(id=equipment_id)
        except Equipment.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Equipment with ID {equipment_id} not found")
            )
            return

        self.stdout.write(f"Syncing equipment: {equipment.name}")

        if not equipment.monitoring_enabled:
            if equipment.zabbix_hostid:
                result = service.delete_host(equipment.zabbix_hostid)
                if result['success']:
                    equipment.zabbix_hostid = None
                    equipment.save()
                    self.stdout.write("🗑️ Removed from monitoring (disabled)")
            else:
                self.stdout.write("⚠️ Equipment monitoring is disabled")
            return

        if not equipment.ip_address:
            self.stdout.write(
                self.style.ERROR("❌ Equipment must have an IP address for monitoring")
            )
            return

        if equipment.zabbix_hostid:
            result = service.update_host(equipment)
            action = "Updated"
        else:
            result = service.create_host(equipment)
            if result['success']:
                equipment.zabbix_hostid = result['hostid']
                equipment.save()
            action = "Created"

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ {action} host successfully")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to {action.lower()} host: {result['error']}")
            )

    def update_monitoring_data(self, service):
        """Update monitoring data for existing hosts"""
        equipment_with_hosts = Equipment.objects.filter(
            zabbix_hostid__isnull=False,
            monitoring_enabled=True
        )

        self.stdout.write(f"Updating data for {equipment_with_hosts.count()} monitored equipment...")

        for equipment in equipment_with_hosts:
            try:
                result = service.get_host_data(equipment.zabbix_hostid)
                if result['success']:
                    self.stdout.write(f"✅ Updated data for {equipment.name}")
                else:
                    self.stdout.write(f"⚠️ Could not get data for {equipment.name}: {result['error']}")
            except Exception as e:
                self.stdout.write(f"❌ Error updating {equipment.name}: {e}")

    def cleanup_disabled_equipment(self, service):
        """Remove disabled equipment from Zabbix"""
        disabled_with_hosts = Equipment.objects.filter(
            monitoring_enabled=False,
            zabbix_hostid__isnull=False
        )

        self.stdout.write(f"Cleaning up {disabled_with_hosts.count()} disabled equipment...")

        for equipment in disabled_with_hosts:
            try:
                result = service.delete_host(equipment.zabbix_hostid)
                if result['success']:
                    equipment.zabbix_hostid = None
                    equipment.save()
                    self.stdout.write(f"🗑️ Removed {equipment.name}")
            except Exception as e:
                self.stdout.write(f"❌ Error removing {equipment.name}: {e}")