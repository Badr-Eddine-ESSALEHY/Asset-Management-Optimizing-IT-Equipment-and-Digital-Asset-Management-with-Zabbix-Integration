# zabbix/client.py - Main Zabbix API client

import json
import logging
import requests
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.core.cache import cache
from pyzabbix import ZabbixAPI, ZabbixAPIException

logger = logging.getLogger(__name__)


class ZabbixClient:
    """
    Enhanced Zabbix API client with caching and error handling
    """

    def __init__(self):
        self.config = settings.ZABBIX_CONFIG
        self.api = None
        self._authenticated = False
        self.session = requests.Session()
        self.session.verify = self.config.get('VERIFY_SSL', False)

    def connect(self) -> bool:
        """
        Establish connection to Zabbix API
        """
        try:
            self.api = ZabbixAPI(
                server=self.config['URL'],
                timeout=self.config.get('TIMEOUT', 30)
            )

            # Disable SSL warnings if not verifying
            if not self.config.get('VERIFY_SSL', False):
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            self.api.login(
                self.config['USERNAME'],
                self.config['PASSWORD']
            )

            self._authenticated = True
            logger.info("Successfully connected to Zabbix API")
            return True

        except ZabbixAPIException as e:
            logger.error(f"Zabbix API authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        """
        Close Zabbix API connection
        """
        if self.api and self._authenticated:
            try:
                self.api.user.logout()
                self._authenticated = False
                logger.info("Disconnected from Zabbix API")
            except Exception as e:
                logger.error(f"Logout error: {e}")

    def _ensure_connection(self):
        """
        Ensure API connection is active
        """
        if not self._authenticated:
            if not self.connect():
                raise Exception("Failed to connect to Zabbix API")

    def get_hosts(self, **kwargs) -> List[Dict]:
        """
        Get all hosts with optional filters
        """
        cache_key = f"zabbix_hosts_{hash(str(kwargs))}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            params = {
                'output': ['hostid', 'host', 'name', 'status', 'available', 'description'],
                'selectInterfaces': ['interfaceid', 'ip', 'dns', 'port', 'type'],
                'selectTags': ['tag', 'value'],
                **kwargs
            }

            hosts = self.api.host.get(**params)

            # Cache for 1 minute
            cache.set(cache_key, hosts, 60)

            return hosts

        except ZabbixAPIException as e:
            logger.error(f"Failed to get hosts: {e}")
            return []

    def get_problems(self, **kwargs) -> List[Dict]:
        """
        Get current problems/issues
        """
        cache_key = f"zabbix_problems_{hash(str(kwargs))}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            params = {
                'output': 'extend',
                'selectHosts': ['hostid', 'host', 'name'],
                'selectTags': ['tag', 'value'],
                'recent': 'true',
                'sortfield': ['eventid'],
                'sortorder': 'DESC',
                **kwargs
            }

            problems = self.api.problem.get(**params)

            # Cache for 30 seconds (real-time data)
            cache.set(cache_key, problems, 30)

            return problems

        except ZabbixAPIException as e:
            logger.error(f"Failed to get problems: {e}")
            return []

    def get_items(self, hostids: List[str] = None, **kwargs) -> List[Dict]:
        """
        Get items (metrics) for specified hosts
        """
        cache_key = f"zabbix_items_{hash(str((hostids, kwargs)))}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            params = {
                'output': ['itemid', 'hostid', 'name', 'key_', 'value_type', 'units', 'description'],
                'selectHosts': ['hostid', 'host', 'name'],
                'monitored': True,
                **kwargs
            }

            if hostids:
                params['hostids'] = hostids

            items = self.api.item.get(**params)

            # Cache for 2 minutes
            cache.set(cache_key, items, 120)

            return items

        except ZabbixAPIException as e:
            logger.error(f"Failed to get items: {e}")
            return []

    def get_latest_data(self, itemids: List[str]) -> List[Dict]:
        """
        Get latest values for specified items
        """
        cache_key = f"zabbix_latest_{hash(str(itemids))}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            latest_data = self.api.item.get(
                output=['itemid', 'lastvalue', 'lastclock', 'units'],
                itemids=itemids,
                selectHosts=['hostid', 'host', 'name']
            )

            # Cache for 15 seconds (real-time)
            cache.set(cache_key, latest_data, 15)

            return latest_data

        except ZabbixAPIException as e:
            logger.error(f"Failed to get latest data: {e}")
            return []

    def get_triggers(self, hostids: List[str] = None, **kwargs) -> List[Dict]:
        """
        Get triggers for monitoring conditions
        """
        cache_key = f"zabbix_triggers_{hash(str((hostids, kwargs)))}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            params = {
                'output': ['triggerid', 'description', 'status', 'priority', 'value', 'lastchange'],
                'selectHosts': ['hostid', 'host', 'name'],
                'selectItems': ['itemid', 'name', 'key_'],
                'monitored': True,
                'skipDependent': True,
                **kwargs
            }

            if hostids:
                params['hostids'] = hostids

            triggers = self.api.trigger.get(**params)

            # Cache for 1 minute
            cache.set(cache_key, triggers, 60)

            return triggers

        except ZabbixAPIException as e:
            logger.error(f"Failed to get triggers: {e}")
            return []

    def get_events(self, limit: int = 100, **kwargs) -> List[Dict]:
        """
        Get recent events
        """
        cache_key = f"zabbix_events_{hash(str((limit, kwargs)))}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            params = {
                'output': 'extend',
                'selectHosts': ['hostid', 'host', 'name'],
                'sortfield': ['clock'],
                'sortorder': 'DESC',
                'limit': limit,
                **kwargs
            }

            events = self.api.event.get(**params)

            # Cache for 15 seconds
            cache.set(cache_key, events, 15)

            return events

        except ZabbixAPIException as e:
            logger.error(f"Failed to get events: {e}")
            return []

    def get_host_groups(self) -> List[Dict]:
        """
        Get all host groups
        """
        cache_key = "zabbix_host_groups"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        self._ensure_connection()

        try:
            groups = self.api.hostgroup.get(
                output=['groupid', 'name'],
                real_hosts=True
            )

            # Cache for 5 minutes
            cache.set(cache_key, groups, 300)

            return groups

        except ZabbixAPIException as e:
            logger.error(f"Failed to get host groups: {e}")
            return []

    def acknowledge_problem(self, eventid: str, message: str, user: str) -> bool:
        """
        Acknowledge a problem event
        """
        self._ensure_connection()

        try:
            result = self.api.event.acknowledge(
                eventids=eventid,
                action=6,  # Add message and acknowledge
                message=f"Acknowledged by {user}: {message}"
            )

            logger.info(f"Problem {eventid} acknowledged by {user}")

            # Clear related cache
            cache.delete_pattern("zabbix_problems_*")

            return True

        except ZabbixAPIException as e:
            logger.error(f"Failed to acknowledge problem {eventid}: {e}")
            return False

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get summary data for dashboard
        """
        cache_key = "zabbix_dashboard_summary"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        try:
            # Get all data in parallel
            hosts = self.get_hosts()
            problems = self.get_problems()

            # Calculate summary statistics
            total_hosts = len(hosts)
            enabled_hosts = len([h for h in hosts if h.get('status') == '0'])
            disabled_hosts = total_hosts - enabled_hosts

            problem_count = len(problems)
            critical_problems = len([p for p in problems if p.get('severity') in ['4', '5']])

            summary = {
                'total_hosts': total_hosts,
                'enabled_hosts': enabled_hosts,
                'disabled_hosts': disabled_hosts,
                'total_problems': problem_count,
                'critical_problems': critical_problems,
                'last_updated': cache.get('zabbix_last_update', 'Never')
            }

            # Cache for 30 seconds
            cache.set(cache_key, summary, 30)
            cache.set('zabbix_last_update', 'Just now', 30)

            return summary

        except Exception as e:
            logger.error(f"Failed to get dashboard summary: {e}")
            return {
                'total_hosts': 0,
                'enabled_hosts': 0,
                'disabled_hosts': 0,
                'total_problems': 0,
                'critical_problems': 0,
                'last_updated': 'Error'
            }


# Global client instance
zabbix_client = ZabbixClient()