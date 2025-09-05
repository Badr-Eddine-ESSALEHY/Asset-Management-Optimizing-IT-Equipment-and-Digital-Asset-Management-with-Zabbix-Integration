#!/bin/bash
# Quick setup script to run after Zabbix installation is complete

echo "=== Django-Zabbix Integration Setup ==="

# Get Django project path
read -p "Enter your Django project directory path: " PROJECT_DIR
read -p "Enter your Ubuntu server IP address: " SERVER_IP

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Project directory does not exist!"
    exit 1
fi

cd "$PROJECT_DIR"

echo "Creating integration directories..."
mkdir -p assets/services
mkdir -p assets/management/commands
mkdir -p templates/assets

echo "Installing Python packages..."
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../django_zabbix_env" ]; then
    source ../django_zabbix_env/bin/activate
fi

pip install -r requirements.txt

echo "Creating settings configuration..."
cat >> local_settings.py << EOF

# Zabbix Integration Settings
ZABBIX_CONFIG = {
    'SERVER': 'http://$SERVER_IP/zabbix/api_jsonrpc.php',
    'USERNAME': 'Admin',
    'PASSWORD': 'zabbix',  # Change this after setup!
    'SNMP_COMMUNITY': 'public',  # Change for production!
    'SNMP_VERSION': '2c',
}

# Celery Configuration
CELERY_BROKER_URL = 'redis://$SERVER_IP:6379/0'
CELERY_RESULT_BACKEND = 'redis://$SERVER_IP:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Celery Beat Schedule
CELERY_BEAT_SCHEDULE = {
    'bulk-sync-monitoring': {
        'task': 'assets.tasks.bulk_sync_monitoring',
        'schedule': 3600.0,  # Every hour
    },
    'update-monitoring-data': {
        'task': 'assets.tasks.update_monitoring_data',
        'schedule': 300.0,  # Every 5 minutes
    },
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'zabbix_integration.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'assets.services.zabbix_service': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'assets.tasks': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

EOF

echo "Don't forget to:"
echo "1. Add 'from .local_settings import *' to your settings.py"
echo "2. Copy the integration Python files to your project"
echo "3. Update your URLs to include monitoring paths"
echo "4. Run migrations: python manage.py migrate"
echo "5. Test connection: python manage.py sync_zabbix --test-connection"

echo "Setup script completed!"