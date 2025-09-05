from celery import shared_task
from django.utils import timezone
from assets.models import Equipment
from assets.services.zabbix_service import ZabbixIntegrationService
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, retry_backoff=True, max_retries=3)
def sync_equipment_to_zabbix(self, equipment_id):
    """Celery task to sync single equipment to Zabbix"""
    try:
        equipment = Equipment.objects.get(id=equipment_id)
        service = ZabbixIntegrationService()

        if equipment.monitoring_enabled and equipment.ip_address:
            if equipment.zabbix_hostid:
                result = service.update_host(equipment)
                action = "updated"
            else:
                result = service.create_host(equipment)
                if result['success']:
                    equipment.zabbix_hostid = result['hostid']
                    equipment.save()
                action = "created"

            logger.info(f"Equipment {equipment_id} {action}: {result}")
            return result
        else:
            # Remove from monitoring if disabled
            if equipment.zabbix_hostid:
                result = service.delete_host(equipment.zabbix_hostid)
                if result['success']:
                    equipment.zabbix_hostid = None
                    equipment.save()
                logger.info(f"Equipment {equipment_id} removed from monitoring")
                return result

        return {"success": True, "message": "No action needed"}

    except Equipment.DoesNotExist:
        logger.error(f"Equipment {equipment_id} not found")
        return {"success": False, "error": "Equipment not found"}
    except Exception as e:
        logger.error(f"Error syncing equipment {equipment_id}: {e}")
        # Retry the task
        raise self.retry(exc=e, countdown=60)


@shared_task
def bulk_sync_monitoring():
    """Periodic task to sync all equipment with Zabbix"""
    try:
        service = ZabbixIntegrationService()

        # Test API connection first
        if not service.test_connection()['success']:
            logger.error("Cannot connect to Zabbix API for bulk sync")
            return {"success": False, "error": "API connection failed"}

        results = {
            "success_count": 0,
            "error_count": 0,
            "processed": []
        }

        # Sync enabled equipment
        enabled_equipment = Equipment.objects.filter(
            monitoring_enabled=True,
            ip_address__isnull=False
        ).exclude(ip_address='')

        for equipment in enabled_equipment:
            try:
                if equipment.zabbix_hostid:
                    result = service.update_host(equipment)
                else:
                    result = service.create_host(equipment)
                    if result['success']:
                        equipment.zabbix_hostid = result['hostid']
                        equipment.save()

                if result['success']:
                    results["success_count"] += 1
                else:
                    results["error_count"] += 1

                results["processed"].append({
                    "equipment_id": equipment.id,
                    "name": equipment.name,
                    "success": result['success'],
                    "message": result.get('message', result.get('error', ''))
                })

            except Exception as e:
                results["error_count"] += 1
                results["processed"].append({
                    "equipment_id": equipment.id,
                    "name": equipment.name,
                    "success": False,
                    "message": str(e)
                })

        # Clean up disabled equipment
        disabled_equipment = Equipment.objects.filter(
            monitoring_enabled=False,
            zabbix_hostid__isnull=False
        )
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
                    results["success_count"] += 1
                else:
                    results["error_count"] += 1

                results["processed"].append({
                    "equipment_id": equipment.id,
                    "name": equipment.name,
                    "success": result['success'],
                    "message": result.get('message', result.get('error', ''))
                })

            except Exception as e:
                results["error_count"] += 1
                results["processed"].append({
                    "equipment_id": equipment.id,
                    "name": equipment.name,
                    "success": False,
                    "message": str(e)
                })

        logger.info(f"Bulk sync completed: {results}")
        return {"success": True, "results": results}

    except Exception as e:
        logger.error(f"Error in bulk_sync_monitoring: {e}")
        return {"success": False, "error": str(e)}