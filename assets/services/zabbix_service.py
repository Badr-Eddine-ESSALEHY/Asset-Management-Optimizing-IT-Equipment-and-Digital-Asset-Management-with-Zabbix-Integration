import logging
from typing import Dict, List, Optional
import datetime


from pysnmp.hlapi.v3arch import ContextData, UdpTransportTarget
from pysnmp.entity.engine import SnmpEngine
from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity
from pysnmp.hlapi.v1arch import CommunityData
from zabbix_utils import ZabbixAPI
from django.conf import settings
from django.core.cache import cache
from assets.models import Equipment
from celery import shared_task

logger = logging.getLogger(__name__)


class ZabbixService:
    """Service class for Zabbix API interactions"""

    def __init__(self):
        self.api = None
        self.connect()

    def connect(self) -> bool:
        """Connect to Zabbix API"""
        try:
            self.api = ZabbixAPI(
                server=settings.ZABBIX_CONFIG['SERVER'],
                user=settings.ZABBIX_CONFIG['USERNAME'],
                password=settings.ZABBIX_CONFIG['PASSWORD']
            )
            logger.info("Successfully connected to Zabbix API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zabbix: {e}")
            return False

    def get_history_data(self, hostid: str, metric: str, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get historical data for a specific metric"""
        try:
            if not self.api:
                return []

            # Get item by key
            items = self.api.item.get(
                hostids=hostid,
                search={'key_': metric},
                output=['itemid', 'name', 'key_']
            )

            if not items:
                return []

            itemid = items[0]['itemid']

            # Get history data
            history = self.api.history.get(
                itemids=itemid,
                time_from=int(start_time.timestamp()),
                time_till=int(end_time.timestamp()),
                sortfield='clock',
                sortorder='ASC'
            )

            return history

        except Exception as e:
            logger.error(f"Failed to get history data for {metric}: {e}")
            return []

    def get_host_info(self, hostid: str) -> Dict:
        """Get host information"""
        try:
            if not self.api:
                return {}

            host = self.api.host.get(
                hostids=hostid,
                output=['hostid', 'host', 'name', 'status'],
                selectInterfaces=['interfaceid', 'ip', 'dns', 'port']
            )

            return host[0] if host else {}

        except Exception as e:
            logger.error(f"Failed to get host info for {hostid}: {e}")
            return {}


class ZabbixIntegrationService(ZabbixService):
    """Extended service class for Zabbix integration with Django asset management"""

    def test_snmp_connectivity(self, ip_address: str, community: str = None) -> Dict:
        """Test SNMP connectivity to a device"""
        if not community:
            community = settings.ZABBIX_CONFIG['SNMP_COMMUNITY']

        # try:
        #     iterator = getCmd(
        #         SnmpEngine(),
        #         CommunityData(community),
        #         UdpTransportTarget((ip_address, 161)),
        #         ContextData(),
        #         ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')),  # System description
        #         ObjectType(ObjectIdentity('1.3.6.1.2.1.1.5.0')),  # System name
        #         ObjectType(ObjectIdentity('1.3.6.1.2.1.1.3.0')),  # System uptime
        #     )
        #
        #     errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        #
        #     if errorIndication:
        #         return {'success': False, 'error': str(errorIndication)}
        #     elif errorStatus:
        #         return {'success': False,
        #                 'error': f'{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or "?"}'}
        #
        #     result = {'success': True, 'data': {}}
        #     for varBind in varBinds:
        #         oid, value = varBind
        #         if '1.3.6.1.2.1.1.1.0' in str(oid):
        #             result['data']['description'] = str(value)
        #         elif '1.3.6.1.2.1.1.5.0' in str(oid):
        #             result['data']['hostname'] = str(value)
        #         elif '1.3.6.1.2.1.1.3.0' in str(oid):
        #             result['data']['uptime'] = str(value)
        #
        #     return result
        #
        # except Exception as e:
        #     return {'success': False, 'error': str(e)}

    def create_host_group(self, group_name: str) -> Optional[str]:
        """Create a host group in Zabbix"""
        try:
            # Check if group exists
            existing = self.api.hostgroup.get(filter={'name': group_name})
            if existing:
                return existing[0]['groupid']

            # Create new group
            result = self.api.hostgroup.create(name=group_name)
            return result['groupids'][0]
        except Exception as e:
            logger.error(f"Failed to create host group {group_name}: {e}")
            return None

    def create_or_update_host(self, equipment: Equipment) -> Dict:
        """Create or update a host in Zabbix based on Equipment model"""
        try:
            if not equipment.ip_address:
                return {'success': False, 'error': 'No IP address provided'}

            # Test SNMP connectivity first
            snmp_test = self.test_snmp_connectivity(equipment.ip_address)
            if not snmp_test['success']:
                return {'success': False, 'error': f'SNMP test failed: {snmp_test["error"]}'}

            # Create host group based on location and category
            group_name = f"{equipment.location.name if equipment.location else 'Unknown'} - {equipment.category}"
            group_id = self.create_host_group(group_name)

            if not group_id:
                group_id = self.create_host_group("Default")

            # Check if host already exists
            existing_host = None
            if equipment.zabbix_hostid:
                try:
                    existing_host = self.api.host.get(
                        hostids=equipment.zabbix_hostid,
                        output=['hostid', 'host', 'name']
                    )
                    if not existing_host:
                        equipment.zabbix_hostid = None
                except:
                    equipment.zabbix_hostid = None

            host_data = {
                'host': equipment.hostname or f"equipment-{equipment.id}",
                'name': f"{equipment.name} ({equipment.asset_tag})" if equipment.asset_tag else equipment.name,
                'interfaces': [{
                    'type': 2,  # SNMP interface
                    'main': 1,
                    'useip': 1,
                    'ip': equipment.ip_address,
                    'dns': '',
                    'port': '161',
                    'details': {
                        'version': 2,
                        'community': settings.ZABBIX_CONFIG['SNMP_COMMUNITY']
                    }
                }],
                'groups': [{'groupid': group_id}],
                'templates': self._get_templates_for_equipment(equipment),
                'inventory_mode': 1,  # Manual inventory
                'inventory': self._build_inventory_data(equipment)
            }

            if existing_host:
                # Update existing host
                host_data['hostid'] = equipment.zabbix_hostid
                result = self.api.host.update(**host_data)
                host_id = equipment.zabbix_hostid
            else:
                # Create new host
                result = self.api.host.create(**host_data)
                host_id = result['hostids'][0]

                # Update equipment with Zabbix host ID
                equipment.zabbix_hostid = host_id
                equipment.save(update_fields=['zabbix_hostid'])

            return {
                'success': True,
                'host_id': host_id,
                'snmp_data': snmp_test['data']
            }

        except Exception as e:
            logger.error(f"Failed to create/update host for equipment {equipment.id}: {e}")
            return {'success': False, 'error': str(e)}

    def _get_templates_for_equipment(self, equipment: Equipment) -> List[Dict]:
        """Get appropriate templates based on equipment category"""
        template_map = {
            'server': ['Linux by SNMP', 'Generic SNMP'],
            'laptop': ['Generic SNMP'],
            'desktop': ['Generic SNMP'],
            'network': ['Network interfaces by SNMP', 'Generic SNMP'],
            'printer': ['Printer Generic by SNMP'],
            'ups': ['UPS by SNMP'],
        }

        templates = template_map.get(equipment.category.lower(), ['Generic SNMP'])
        template_objects = []

        for template_name in templates:
            try:
                template = self.api.template.get(filter={'host': template_name})
                if template:
                    template_objects.append({'templateid': template[0]['templateid']})
            except Exception as e:
                logger.warning(f"Template {template_name} not found: {e}")

        # Fallback to Generic SNMP if no templates found
        if not template_objects:
            try:
                template = self.api.template.get(filter={'host': 'Generic SNMP'})
                if template:
                    template_objects.append({'templateid': template[0]['templateid']})
            except Exception as e:
                logger.error(f"Failed to find Generic SNMP template: {e}")

        return template_objects

    def _build_inventory_data(self, equipment: Equipment) -> Dict:
        """Build inventory data for Zabbix from Equipment model"""
        return {
            'name': equipment.name,
            'type': equipment.category,
            'tag': equipment.asset_tag or '',
            'asset_tag': equipment.asset_tag or '',
            'macaddress_a': equipment.mac_address or '',
            'serialno_a': equipment.serial_number or '',
            'hardware': f"{equipment.manufacturer} {equipment.model}",
            'vendor': equipment.manufacturer,
            'model': equipment.model,
            'location': equipment.location.name if equipment.location else '',
            'location_lat': '',
            'location_lon': '',
            'notes': equipment.notes,
            'chassis': equipment.specifications,
            'contact': equipment.assigned_to.email if equipment.assigned_to else '',
            'site_address_a': equipment.location.description if equipment.location else '',
            'site_address_b': '',
            'site_address_c': '',
            'date_hw_purchase': equipment.purchase_date.strftime('%Y-%m-%d') if equipment.purchase_date else '',
            'date_hw_install': equipment.assigned_date.strftime('%Y-%m-%d') if equipment.assigned_date else '',
            'date_hw_expiry': equipment.warranty_expiration.strftime(
                '%Y-%m-%d') if equipment.warranty_expiration else '',
            'hw_arch': '',
            'software': '',
            'software_app_a': '',
            'software_app_b': '',
            'software_app_c': '',
            'software_app_d': '',
            'software_app_e': '',
        }

    def get_host_monitoring_data(self, zabbix_hostid: str, hours: int = 24) -> Dict:
        """Get monitoring data for a specific host"""
        try:
            # Get host info
            host = self.api.host.get(
                hostids=zabbix_hostid,
                output=['hostid', 'host', 'name', 'status']
            )[0]

            # Get items for the host
            items = self.api.item.get(
                hostids=zabbix_hostid,
                output=['itemid', 'name', 'key_', 'lastvalue', 'units', 'lastclock'],
                monitored=True,
                limit=50
            )

            # Get triggers
            triggers = self.api.trigger.get(
                hostids=zabbix_hostid,
                output=['triggerid', 'description', 'status', 'value', 'priority'],
                active=True,
                monitored=True
            )

            # Get recent history for key items
            time_from = int((datetime.datetime.now() - datetime.timedelta(hours=hours)).timestamp())

            history_data = {}
            for item in items[:10]:  # Limit to first 10 items to avoid overload
                try:
                    history = self.api.history.get(
                        itemids=item['itemid'],
                        time_from=time_from,
                        limit=100,
                        sortfield='clock',
                        sortorder='DESC'
                    )
                    if history:
                        history_data[item['name']] = history
                except Exception as e:
                    logger.warning(f"Failed to get history for item {item['name']}: {e}")

            return {
                'success': True,
                'host': host,
                'items': items,
                'triggers': triggers,
                'history': history_data
            }

        except Exception as e:
            logger.error(f"Failed to get monitoring data for host {zabbix_hostid}: {e}")
            return {'success': False, 'error': str(e)}

    def delete_host(self, zabbix_hostid: str) -> bool:
        """Delete a host from Zabbix"""
        try:
            self.api.host.delete(zabbix_hostid)
            return True
        except Exception as e:
            logger.error(f"Failed to delete host {zabbix_hostid}: {e}")
            return False


# Celery tasks for async operations
@shared_task
def sync_equipment_to_zabbix(equipment_id: int):
    """Async task to sync equipment to Zabbix"""
    try:
        equipment = Equipment.objects.get(id=equipment_id)
        if not equipment.monitoring_enabled:
            return {'success': False, 'error': 'Monitoring not enabled for this equipment'}

        service = ZabbixIntegrationService()
        result = service.create_or_update_host(equipment)

        if result['success']:
            logger.info(f"Successfully synced equipment {equipment_id} to Zabbix")
        else:
            logger.error(f"Failed to sync equipment {equipment_id}: {result['error']}")

        return result

    except Equipment.DoesNotExist:
        return {'success': False, 'error': 'Equipment not found'}
    except Exception as e:
        logger.error(f"Error syncing equipment {equipment_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def bulk_sync_equipment():
    """Sync all monitoring-enabled equipment to Zabbix"""
    equipment_list = Equipment.objects.filter(
        monitoring_enabled=True,
        ip_address__isnull=False
    ).exclude(ip_address='')

    results = []
    service = ZabbixIntegrationService()

    for equipment in equipment_list:
        try:
            result = service.create_or_update_host(equipment)
            results.append({
                'equipment_id': equipment.id,
                'name': equipment.name,
                'result': result
            })
        except Exception as e:
            results.append({
                'equipment_id': equipment.id,
                'name': equipment.name,
                'result': {'success': False, 'error': str(e)}
            })

    return results


@shared_task
def update_monitoring_data():
    """Update monitoring data from Zabbix for all monitored equipment"""
    equipment_list = Equipment.objects.filter(
        monitoring_enabled=True,
        zabbix_hostid__isnull=False
    ).exclude(zabbix_hostid='')

    service = ZabbixIntegrationService()
    results = []

    for equipment in equipment_list:
        try:
            data = service.get_host_monitoring_data(equipment.zabbix_hostid)

            # Cache the monitoring data
            cache_key = f"monitoring_data_{equipment.id}"
            cache.set(cache_key, data, timeout=300)  # 5 minutes

            results.append({
                'equipment_id': equipment.id,
                'success': data['success']
            })

        except Exception as e:
            logger.error(f"Failed to update monitoring data for equipment {equipment.id}: {e}")
            results.append({
                'equipment_id': equipment.id,
                'success': False,
                'error': str(e)
            })

    return results