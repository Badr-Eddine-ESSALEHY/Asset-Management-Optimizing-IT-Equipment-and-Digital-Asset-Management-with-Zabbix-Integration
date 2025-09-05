# assets/predictive_maintenance.py
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Avg, Max, Min, Count
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import warnings

warnings.filterwarnings('ignore')

from .models import Equipment, Intervention
from .services.zabbix_service import ZabbixService
from messages.models import SystemNotification
from messages.consumers import send_system_notification

logger = logging.getLogger(__name__)


class PredictiveMaintenanceService:
    """AI-powered predictive maintenance system using Zabbix monitoring data"""

    def __init__(self):
        self.zabbix_service = ZabbixService()
        self.scaler = StandardScaler()

        # Thresholds for different alert types
        self.thresholds = {
            'cpu_critical': 90,
            'cpu_warning': 80,
            'memory_critical': 95,
            'memory_warning': 85,
            'disk_critical': 95,
            'disk_warning': 85,
            'temperature_critical': 80,
            'temperature_warning': 70,
            'network_error_rate': 0.05,
            'uptime_threshold': 30  # days
        }

    def analyze_equipment_health(self, equipment_id: int, days: int = 30) -> dict:
        """
        Analyze equipment health and predict maintenance needs

        Returns:
        {
            'health_score': float (0-100),
            'risk_level': str ('low', 'medium', 'high', 'critical'),
            'predicted_failure_date': datetime or None,
            'maintenance_recommendations': List[str],
            'anomalies': List[dict],
            'trends': dict
        }
        """
        try:
            equipment = Equipment.objects.get(id=equipment_id)

            if not equipment.monitoring_enabled or not equipment.zabbix_hostid:
                return {
                    'health_score': 50,
                    'risk_level': 'unknown',
                    'predicted_failure_date': None,
                    'maintenance_recommendations': ['Enable monitoring to get health insights'],
                    'anomalies': [],
                    'trends': {}
                }

            # Get monitoring data from Zabbix
            monitoring_data = self._get_monitoring_data(equipment, days)

            if not monitoring_data:
                return self._create_no_data_response()

            # Perform various analyses
            health_metrics = self._calculate_health_metrics(monitoring_data)
            anomalies = self._detect_anomalies(monitoring_data)
            trends = self._analyze_trends(monitoring_data)
            failure_prediction = self._predict_failure(monitoring_data, equipment)
            recommendations = self._generate_maintenance_recommendations(
                equipment, health_metrics, anomalies, trends
            )

            # Calculate overall health score
            health_score = self._calculate_health_score(health_metrics, anomalies)
            risk_level = self._determine_risk_level(health_score, anomalies)

            result = {
                'health_score': health_score,
                'risk_level': risk_level,
                'predicted_failure_date': failure_prediction,
                'maintenance_recommendations': recommendations,
                'anomalies': anomalies,
                'trends': trends,
                'health_metrics': health_metrics
            }

            # Log significant findings
            if risk_level in ['high', 'critical']:
                logger.warning(f"Equipment {equipment.name} ({equipment.asset_tag}) "
                               f"has {risk_level} risk level with health score {health_score}")

                # Send alert notification
                self._send_maintenance_alert(equipment, result)

            return result

        except Equipment.DoesNotExist:
            return {'error': 'Equipment not found'}
        except Exception as e:
            logger.error(f"Health analysis failed for equipment {equipment_id}: {e}")
            return {'error': str(e)}

    def _get_monitoring_data(self, equipment: Equipment, days: int) -> dict:
        """Fetch monitoring data from Zabbix"""
        try:
            end_time = timezone.now()
            start_time = end_time - timedelta(days=days)

            # Define metrics to collect
            metrics = [
                'system.cpu.util',
                'vm.memory.util',
                'vfs.fs.size[/,pused]',
                'system.hw.chassis[info]',
                'system.uptime',
                'net.if.in[eth0]',
                'net.if.out[eth0]',
                'sensor.temp.value'
            ]

            data = {}
            for metric in metrics:
                try:
                    values = self.zabbix_service.get_history_data(
                        equipment.zabbix_hostid,
                        metric,
                        start_time,
                        end_time
                    )
                    if values:
                        data[metric] = values
                except Exception as e:
                    logger.debug(f"Could not fetch {metric} for {equipment.name}: {e}")
                    continue

            return data

        except Exception as e:
            logger.error(f"Failed to fetch monitoring data: {e}")
            return {}

    def _calculate_health_metrics(self, monitoring_data: dict) -> dict:
        """Calculate key health metrics from monitoring data"""
        metrics = {}

        try:
            # CPU utilization analysis
            if 'system.cpu.util' in monitoring_data:
                cpu_data = [float(v['value']) for v in monitoring_data['system.cpu.util']]
                metrics['cpu'] = {
                    'avg': np.mean(cpu_data),
                    'max': np.max(cpu_data),
                    'p95': np.percentile(cpu_data, 95),
                    'trend': self._calculate_trend(cpu_data)
                }

            # Memory utilization analysis
            if 'vm.memory.util' in monitoring_data:
                memory_data = [float(v['value']) for v in monitoring_data['vm.memory.util']]
                metrics['memory'] = {
                    'avg': np.mean(memory_data),
                    'max': np.max(memory_data),
                    'p95': np.percentile(memory_data, 95),
                    'trend': self._calculate_trend(memory_data)
                }

            # Disk utilization analysis
            if 'vfs.fs.size[/,pused]' in monitoring_data:
                disk_data = [float(v['value']) for v in monitoring_data['vfs.fs.size[/,pused]']]
                metrics['disk'] = {
                    'avg': np.mean(disk_data),
                    'max': np.max(disk_data),
                    'trend': self._calculate_trend(disk_data)
                }

            # Uptime analysis
            if 'system.uptime' in monitoring_data:
                uptime_data = [float(v['value']) for v in monitoring_data['system.uptime']]
                # Convert to days
                uptime_days = [u / (24 * 3600) for u in uptime_data]
                metrics['uptime'] = {
                    'current_days': uptime_days[-1] if uptime_days else 0,
                    'avg_days': np.mean(uptime_days),
                    'restarts': len([u for u in uptime_days if u < 1])  # Systems with < 1 day uptime
                }

            # Temperature analysis (if available)
            if 'sensor.temp.value' in monitoring_data:
                temp_data = [float(v['value']) for v in monitoring_data['sensor.temp.value']]
                metrics['temperature'] = {
                    'avg': np.mean(temp_data),
                    'max': np.max(temp_data),
                    'trend': self._calculate_trend(temp_data)
                }

            # Network analysis
            if 'net.if.in[eth0]' in monitoring_data and 'net.if.out[eth0]' in monitoring_data:
                in_data = [float(v['value']) for v in monitoring_data['net.if.in[eth0]']]
                out_data = [float(v['value']) for v in monitoring_data['net.if.out[eth0]']]

                metrics['network'] = {
                    'avg_in': np.mean(in_data),
                    'avg_out': np.mean(out_data),
                    'max_in': np.max(in_data),
                    'max_out': np.max(out_data),
                    'utilization_trend': self._calculate_trend(np.array(in_data) + np.array(out_data))
                }

        except Exception as e:
            logger.error(f"Error calculating health metrics: {e}")

        return metrics

    def _detect_anomalies(self, monitoring_data: dict) -> list:
        """Detect anomalies in monitoring data using machine learning"""
        anomalies = []

        try:
            # Prepare data for anomaly detection
            for metric_name, metric_data in monitoring_data.items():
                if len(metric_data) < 10:  # Need minimum data points
                    continue

                values = np.array([float(v['value']) for v in metric_data]).reshape(-1, 1)
                timestamps = [v['clock'] for v in metric_data]

                # Use Isolation Forest for anomaly detection
                clf = IsolationForest(contamination=0.1, random_state=42)
                anomaly_labels = clf.fit_predict(values)

                # Find anomalies
                for i, label in enumerate(anomaly_labels):
                    if label == -1:  # Anomaly detected
                        anomalies.append({
                            'metric': metric_name,
                            'timestamp': timestamps[i],
                            'value': values[i][0],
                            'severity': self._calculate_anomaly_severity(metric_name, values[i][0]),
                            'description': self._describe_anomaly(metric_name, values[i][0])
                        })

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")

        # Sort by severity and timestamp
        anomalies.sort(key=lambda x: (x['severity'], x['timestamp']), reverse=True)
        return anomalies[:20]  # Return top 20 anomalies

    def _analyze_trends(self, monitoring_data: dict) -> dict:
        """Analyze trends in monitoring data"""
        trends = {}

        try:
            for metric_name, metric_data in monitoring_data.items():
                if len(metric_data) < 5:
                    continue

                values = [float(v['value']) for v in metric_data]
                timestamps = [v['clock'] for v in metric_data]

                # Calculate trend slope
                trend_slope = self._calculate_trend(values)

                # Determine trend direction and significance
                if abs(trend_slope) < 0.001:
                    trend_direction = 'stable'
                elif trend_slope > 0:
                    trend_direction = 'increasing'
                else:
                    trend_direction = 'decreasing'

                trends[metric_name] = {
                    'direction': trend_direction,
                    'slope': trend_slope,
                    'significance': 'high' if abs(trend_slope) > 0.01 else 'low',
                    'recent_change': (values[-1] - values[0]) / values[0] * 100 if values[0] != 0 else 0
                }

        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")

        return trends

    def _predict_failure(self, monitoring_data: dict, equipment: Equipment) -> datetime:
        """Predict potential failure date based on trends and historical data"""
        try:
            # Get historical intervention data
            past_interventions = Intervention.objects.filter(
                equipment=equipment,
                status='completed'
            ).order_by('-completed_date')[:10]

            if len(past_interventions) < 3:
                return None  # Not enough historical data

            # Calculate average time between interventions
            intervention_intervals = []
            for i in range(1, len(past_interventions)):
                interval = (past_interventions[i - 1].completed_date - past_interventions[i].completed_date).days
                intervention_intervals.append(interval)

            if not intervention_intervals:
                return None

            avg_interval = np.mean(intervention_intervals)
            std_interval = np.std(intervention_intervals)

            # Adjust based on current health trends
            health_factor = 1.0

            # Check for concerning trends
            if 'system.cpu.util' in monitoring_data:
                cpu_data = [float(v['value']) for v in monitoring_data['system.cpu.util']]
                if np.mean(cpu_data) > self.thresholds['cpu_warning']:
                    health_factor *= 0.8  # Reduce predicted interval

            if 'vm.memory.util' in monitoring_data:
                memory_data = [float(v['value']) for v in monitoring_data['vm.memory.util']]
                if np.mean(memory_data) > self.thresholds['memory_warning']:
                    health_factor *= 0.8

            # Calculate predicted failure date
            adjusted_interval = avg_interval * health_factor

            last_intervention = past_interventions[0].completed_date
            predicted_date = last_intervention + timedelta(days=int(adjusted_interval))

            # Don't predict too far in the future
            max_future_date = timezone.now().date() + timedelta(days=365)
            if predicted_date > max_future_date:
                return None

            return predicted_date

        except Exception as e:
            logger.error(f"Failure prediction failed: {e}")
            return None

    def _calculate_health_score(self, health_metrics: dict, anomalies: list) -> float:
        """Calculate overall health score (0-100)"""
        try:
            score = 100.0

            # CPU health impact
            if 'cpu' in health_metrics:
                cpu_avg = health_metrics['cpu']['avg']
                if cpu_avg > self.thresholds['cpu_critical']:
                    score -= 30
                elif cpu_avg > self.thresholds['cpu_warning']:
                    score -= 15

            # Memory health impact
            if 'memory' in health_metrics:
                memory_avg = health_metrics['memory']['avg']
                if memory_avg > self.thresholds['memory_critical']:
                    score -= 25
                elif memory_avg > self.thresholds['memory_warning']:
                    score -= 12

            # Disk health impact
            if 'disk' in health_metrics:
                disk_avg = health_metrics['disk']['avg']
                if disk_avg > self.thresholds['disk_critical']:
                    score -= 20
                elif disk_avg > self.thresholds['disk_warning']:
                    score -= 10

            # Temperature impact
            if 'temperature' in health_metrics:
                temp_avg = health_metrics['temperature']['avg']
                if temp_avg > self.thresholds['temperature_critical']:
                    score -= 25
                elif temp_avg > self.thresholds['temperature_warning']:
                    score -= 10

            # Anomaly impact
            critical_anomalies = [a for a in anomalies if a['severity'] == 'critical']
            high_anomalies = [a for a in anomalies if a['severity'] == 'high']

            score -= len(critical_anomalies) * 10
            score -= len(high_anomalies) * 5

            # Uptime impact
            if 'uptime' in health_metrics:
                if health_metrics['uptime']['restarts'] > 5:  # Frequent restarts
                    score -= 15

            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.error(f"Health score calculation failed: {e}")
            return 50.0

    def _determine_risk_level(self, health_score: float, anomalies: list) -> str:
        """Determine risk level based on health score and anomalies"""
        critical_anomalies = [a for a in anomalies if a['severity'] == 'critical']

        if health_score < 30 or len(critical_anomalies) > 0:
            return 'critical'
        elif health_score < 50:
            return 'high'
        elif health_score < 70:
            return 'medium'
        else:
            return 'low'

    def _generate_maintenance_recommendations(self, equipment: Equipment,
                                              health_metrics: dict, anomalies: list,
                                              trends: dict) -> list:
        """Generate maintenance recommendations"""
        recommendations = []

        try:
            # CPU-based recommendations
            if 'cpu' in health_metrics:
                cpu_avg = health_metrics['cpu']['avg']
                if cpu_avg > self.thresholds['cpu_warning']:
                    recommendations.append(
                        f"High CPU utilization detected ({cpu_avg:.1f}%). "
                        "Consider checking for resource-intensive processes or upgrading hardware."
                    )

            # Memory-based recommendations
            if 'memory' in health_metrics:
                memory_avg = health_metrics['memory']['avg']
                if memory_avg > self.thresholds['memory_warning']:
                    recommendations.append(
                        f"High memory utilization detected ({memory_avg:.1f}%). "
                        "Consider adding more RAM or optimizing memory usage."
                    )

            # Disk-based recommendations
            if 'disk' in health_metrics:
                disk_avg = health_metrics['disk']['avg']
                if disk_avg > self.thresholds['disk_warning']:
                    recommendations.append(
                        f"High disk utilization detected ({disk_avg:.1f}%). "
                        "Consider cleaning up disk space or adding more storage."
                    )

            # Temperature recommendations
            if 'temperature' in health_metrics:
                temp_avg = health_metrics['temperature']['avg']
                if temp_avg > self.thresholds['temperature_warning']:
                    recommendations.append(
                        f"High temperature detected ({temp_avg:.1f}°C). "
                        "Check cooling systems and clean dust from fans."
                    )

            # Trend-based recommendations
            for metric, trend in trends.items():
                if trend['direction'] == 'increasing' and trend['significance'] == 'high':
                    if 'cpu' in metric:
                        recommendations.append("CPU usage is trending upward. Monitor for performance issues.")
                    elif 'memory' in metric:
                        recommendations.append("Memory usage is trending upward. Monitor for memory leaks.")
                    elif 'disk' in metric:
                        recommendations.append("Disk usage is trending upward. Plan for storage expansion.")

            # Anomaly-based recommendations
            critical_anomalies = [a for a in anomalies if a['severity'] == 'critical']
            if critical_anomalies:
                recommendations.append(
                    f"Critical anomalies detected in system metrics. "
                    "Schedule immediate inspection."
                )

            # Historical maintenance recommendations
            if equipment.last_maintenance:
                days_since = (timezone.now().date() - equipment.last_maintenance).days
                if days_since > 90:
                    recommendations.append(
                        f"Last maintenance was {days_since} days ago. "
                        "Schedule routine maintenance check."
                    )

            # Category-specific recommendations
            if equipment.category == 'server':
                recommendations.append("Verify backup systems and disaster recovery procedures.")
            elif equipment.category == 'laptop':
                recommendations.append("Check battery health and consider replacement if degraded.")
            elif equipment.category == 'network':
                recommendations.append("Monitor network traffic patterns and security events.")

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")

        return recommendations[:10]  # Limit to top 10 recommendations

    def _calculate_trend(self, values: list) -> float:
        """Calculate trend slope using linear regression"""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        y = np.array(values)

        # Simple linear regression
        n = len(values)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x ** 2) - (np.sum(x)) ** 2)

        return slope

    def _calculate_anomaly_severity(self, metric_name: str, value: float) -> str:
        """Calculate anomaly severity based on metric and value"""
        if 'cpu' in metric_name:
            if value > 95:
                return 'critical'
            elif value > 85:
                return 'high'
            else:
                return 'medium'
        elif 'memory' in metric_name:
            if value > 98:
                return 'critical'
            elif value > 90:
                return 'high'
            else:
                return 'medium'
        elif 'disk' in metric_name:
            if value > 98:
                return 'critical'
            elif value > 90:
                return 'high'
            else:
                return 'medium'
        elif 'temp' in metric_name:
            if value > 85:
                return 'critical'
            elif value > 75:
                return 'high'
            else:
                return 'medium'

        return 'medium'

    def _describe_anomaly(self, metric_name: str, value: float) -> str:
        """Generate human-readable description of anomaly"""
        if 'cpu' in metric_name:
            return f"Unusually high CPU utilization: {value:.1f}%"
        elif 'memory' in metric_name:
            return f"Unusually high memory utilization: {value:.1f}%"
        elif 'disk' in metric_name:
            return f"Unusually high disk utilization: {value:.1f}%"
        elif 'temp' in metric_name:
            return f"Unusually high temperature: {value:.1f}°C"
        elif 'network' in metric_name:
            return f"Unusual network activity detected: {value:.1f}"
        else:
            return f"Unusual value detected in {metric_name}: {value:.1f}"

    def _send_maintenance_alert(self, equipment: Equipment, analysis_result: dict):
        """Send maintenance alert via messaging system"""
        try:
            # Create system notification
            notification = SystemNotification.objects.create(
                notification_type='maintenance_due',
                title=f"Maintenance Alert: {equipment.name}",
                message=f"Equipment {equipment.name} ({equipment.asset_tag}) requires attention. "
                        f"Health score: {analysis_result['health_score']:.1f}/100. "
                        f"Risk level: {analysis_result['risk_level']}.",
                target_roles="admin,technician",
                related_equipment=equipment,
                action_url=f"/assets/equipment/{equipment.id}/",
                action_text="View Equipment"
            )

            # Send real-time notification
            from asgiref.sync import async_to_sync
            async_to_sync(send_system_notification)(
                'maintenance_due',
                {
                    'equipment': {
                        'id': equipment.id,
                        'name': equipment.name,
                        'asset_tag': equipment.asset_tag,
                    },
                    'health_score': analysis_result['health_score'],
                    'risk_level': analysis_result['risk_level'],
                    'recommendations': analysis_result['maintenance_recommendations'][:3]
                },
                target_roles=['admin', 'technician']
            )

        except Exception as e:
            logger.error(f"Failed to send maintenance alert: {e}")

    def _create_no_data_response(self):
        """Create response when no monitoring data is available"""
        return {
            'health_score': 50,
            'risk_level': 'unknown',
            'predicted_failure_date': None,
            'maintenance_recommendations': [
                'No monitoring data available',
                'Enable Zabbix monitoring to get detailed health insights',
                'Ensure network connectivity to monitoring server'
            ],
            'anomalies': [],
            'trends': {}
        }


# Utility functions for scheduled tasks
def run_predictive_maintenance_analysis():
    """Run predictive maintenance analysis for all monitored equipment"""
    service = PredictiveMaintenanceService()

    # Get all equipment with monitoring enabled
    monitored_equipment = Equipment.objects.filter(
        monitoring_enabled=True,
        status__in=['available', 'assigned']
    ).exclude(zabbix_hostid__isnull=True)

    results = []
    for equipment in monitored_equipment:
        try:
            analysis = service.analyze_equipment_health(equipment.id)
            results.append({
                'equipment_id': equipment.id,
                'equipment_name': equipment.name,
                'analysis': analysis
            })

        except Exception as e:
            logger.error(f"Failed to analyze equipment {equipment.id}: {e}")

    return results