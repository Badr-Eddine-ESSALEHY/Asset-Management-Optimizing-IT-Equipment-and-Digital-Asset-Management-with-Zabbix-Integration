# Django-Zabbix Integration Deployment Checklist

## Prerequisites
- [ ] Ubuntu 22.04 LTS server
- [ ] Django project with Equipment model
- [ ] Network access between Django app and Zabbix server

## Step 1: Install Zabbix Server
- [ ] Run the Zabbix+MariaDB installation script
- [ ] Complete Zabbix web setup at http://server-ip/zabbix
- [ ] Change default admin password from 'zabbix'
- [ ] Test SNMP connectivity: `snmpwalk -v2c -c public localhost 1.3.6.1.2.1.1.1.0`

## Step 2: Install Python Packages
```bash
pip install Django==4.2.16 zabbix-utils==2.0.0 pyzabbix==1.3.1 pysnmp==5.0.29 celery==5.3.4 redis==5.0.1 django-redis==5.4.0 python-decouple==3.8
```

## Step 3: Django Integration Files
- [ ] Create `assets/services/zabbix_service.py`
- [ ] Create `assets/management/commands/sync_zabbix.py`  
- [ ] Create `assets/views_monitoring.py`
- [ ] Create `assets/tasks.py`
- [ ] Update `assets/urls.py` with monitoring URLs
- [ ] Create monitoring templates in `templates/assets/`

## Step 4: Django Configuration
- [ ] Add Zabbix settings to `settings.py`:
```python
ZABBIX_CONFIG = {
    'SERVER': 'http://your-server-ip/zabbix/api_jsonrpc.php',
    'USERNAME': 'Admin', 
    'PASSWORD': 'your-password',
    'SNMP_COMMUNITY': 'your-community',
}
```
- [ ] Configure Celery with Redis
- [ ] Set up logging for Zabbix integration
- [ ] Add monitoring URLs to main `urls.py`

## Step 5: Database Setup
- [ ] Run migrations: `python manage.py migrate`
- [ ] Ensure Equipment model has monitoring fields:
  - `monitoring_enabled`
  - `zabbix_hostid` 
  - `hostname`
  - `ip_address`

## Step 6: Test Integration
- [ ] Test API connection: `python manage.py sync_zabbix --test-connection`
- [ ] Test SNMP: Run test script
- [ ] Enable monitoring on test equipment
- [ ] Sync to Zabbix: `python manage.py sync_zabbix --bulk`

## Step 7: Start Services
- [ ] Start Django development server: `python manage.py runserver`
- [ ] Start Celery worker: `celery -A your_project worker --loglevel=info`  
- [ ] Start Celery beat (optional): `celery -A your_project beat --loglevel=info`

## Step 8: Production Setup (Optional)
- [ ] Configure systemd services for Celery
- [ ] Set up proper web server (nginx/Apache)
- [ ] Configure SSL certificates
- [ ] Set up database backups
- [ ] Configure monitoring alerts
- [ ] Change default passwords and community strings

## Testing URLs
- Django Admin: http://your-django-server/admin/
- Monitoring Dashboard: http://your-django-server/monitoring/
- Zabbix Web: http://your-zabbix-server/zabbix
- Equipment Detail: http://your-django-server/assets/equipment/1/

## Troubleshooting
- Check logs: `tail -f zabbix_integration.log`
- Zabbix server logs: `sudo tail -f /var/log/zabbix/zabbix_server.log`
- Test SNMP manually: `snmpwalk -v2c -c public target-ip 1.3.6.1.2.1.1.1.0`
- Verify Redis: `redis-cli ping`
- Check Celery: `celery -A your_project inspect active`