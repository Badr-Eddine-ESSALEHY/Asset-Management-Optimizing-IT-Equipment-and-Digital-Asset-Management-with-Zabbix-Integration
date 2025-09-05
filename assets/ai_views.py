# assets/ai_views.py
import json
import logging
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .ai_services import AssetCategorizationService, auto_categorize_equipment
from .models import Equipment, Intervention
from .predictive_maintenance import PredictiveMaintenanceService

logger = logging.getLogger(__name__)


@login_required
def ai_dashboard(request):
    """Main AI dashboard with overview and quick actions"""
    try:
        # Get AI statistics
        total_equipment = Equipment.objects.count()
        monitored_equipment = Equipment.objects.filter(monitoring_enabled=True).count()
        uncategorized_equipment = Equipment.objects.filter(category='other').count()

        # Get recent AI activities (you could add an AIAnalysis model to track this)
        recent_analyses = []

        # Get equipment with high risk scores
        service = PredictiveMaintenanceService()
        high_risk_equipment = []

        for equipment in Equipment.objects.filter(monitoring_enabled=True)[:5]:
            try:
                analysis = service.analyze_equipment_health(equipment.id, days=7)
                if analysis.get('risk_level') in ['high', 'critical']:
                    high_risk_equipment.append({
                        'equipment': equipment,
                        'analysis': analysis
                    })
            except Exception as e:
                logger.error(f"Error analyzing {equipment.name}: {e}")
                continue

        # Get categorization statistics
        category_stats = {}
        for category, display in Equipment.EQUIPMENT_CATEGORIES:
            count = Equipment.objects.filter(category=category).count()
            category_stats[display] = count

        context = {
            'total_equipment': total_equipment,
            'monitored_equipment': monitored_equipment,
            'uncategorized_equipment': uncategorized_equipment,
            'monitoring_percentage': round((monitored_equipment / total_equipment * 100) if total_equipment > 0 else 0,
                                           1),
            'recent_analyses': recent_analyses,
            'high_risk_equipment': high_risk_equipment,
            'category_stats': category_stats,
        }

        return render(request, 'assets/ai/dashboard.html', context)

    except Exception as e:
        logger.error(f"AI Dashboard error: {e}")
        messages.error(request, "Error loading AI dashboard")
        return redirect('pages:dashboard')


@login_required
def predictive_maintenance_view(request):
    """Predictive maintenance analysis page"""
    equipment_list = Equipment.objects.filter(monitoring_enabled=True)

    # Filter by risk level if requested
    risk_filter = request.GET.get('risk', 'all')
    search_query = request.GET.get('search', '')

    if search_query:
        equipment_list = equipment_list.filter(name__icontains=search_query)

    # Paginate equipment list
    paginator = Paginator(equipment_list, 10)
    page = request.GET.get('page', 1)
    equipment_page = paginator.get_page(page)

    # Perform analysis for each equipment
    service = PredictiveMaintenanceService()
    analyses = []

    for equipment in equipment_page:
        try:
            analysis = service.analyze_equipment_health(equipment.id, days=30)
            analyses.append({
                'equipment': equipment,
                'analysis': analysis
            })
        except Exception as e:
            logger.error(f"Error analyzing {equipment.name}: {e}")
            analyses.append({
                'equipment': equipment,
                'analysis': {'error': str(e)}
            })

    # Filter by risk level if requested
    if risk_filter != 'all':
        analyses = [a for a in analyses if a['analysis'].get('risk_level') == risk_filter]

    context = {
        'analyses': analyses,
        'equipment_page': equipment_page,
        'risk_filter': risk_filter,
        'search_query': search_query,
        'risk_choices': ['low', 'medium', 'high', 'critical'],
    }

    return render(request, 'assets/ai/predictive_maintenance.html', context)


@login_required
def asset_categorization_view(request):
    """Asset categorization page with AI-powered suggestions"""
    # Get uncategorized or 'other' category equipment
    uncategorized = Equipment.objects.filter(category='other')

    # Get recently categorized items
    recently_categorized = Equipment.objects.exclude(category='other').order_by('-updated_at')[:10]

    # Statistics
    category_stats = {}
    for category, display in Equipment.EQUIPMENT_CATEGORIES:
        count = Equipment.objects.filter(category=category).count()
        category_stats[category] = {
            'display': display,
            'count': count
        }

    context = {
        'uncategorized_equipment': uncategorized,
        'recently_categorized': recently_categorized,
        'category_stats': category_stats,
        'total_equipment': Equipment.objects.count(),
    }

    return render(request, 'assets/ai/asset_categorization.html', context)


@login_required
def image_recognition_view(request):
    """Image-based asset recognition interface"""
    context = {
        'supported_formats': ['jpg', 'jpeg', 'png', 'gif', 'bmp'],
        'max_file_size': '10MB',
    }

    return render(request, 'assets/ai/image_recognition.html', context)


# API Views for AJAX/JavaScript integration

@login_required
@require_POST
def api_run_health_analysis(request, equipment_id=None):
    """API endpoint to run health analysis"""
    try:
        service = PredictiveMaintenanceService()

        if equipment_id:
            # Analyze single equipment
            equipment = get_object_or_404(Equipment, id=equipment_id)
            analysis = service.analyze_equipment_health(equipment_id)

            return JsonResponse({
                'success': True,
                'equipment': {
                    'id': equipment.id,
                    'name': equipment.name,
                    'asset_tag': equipment.asset_tag,
                },
                'analysis': analysis
            })
        else:
            # Analyze all monitored equipment
            equipment_list = Equipment.objects.filter(monitoring_enabled=True)
            results = []

            for equipment in equipment_list[:10]:  # Limit to 10 for performance
                try:
                    analysis = service.analyze_equipment_health(equipment.id)
                    results.append({
                        'equipment': {
                            'id': equipment.id,
                            'name': equipment.name,
                            'asset_tag': equipment.asset_tag,
                        },
                        'analysis': analysis
                    })
                except Exception as e:
                    logger.error(f"Error analyzing {equipment.name}: {e}")
                    continue

            return JsonResponse({
                'success': True,
                'results': results,
                'analyzed_count': len(results)
            })

    except Exception as e:
        logger.error(f"Health analysis API error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def api_auto_categorize(request):
    """API endpoint to auto-categorize assets"""
    try:
        data = json.loads(request.body) if request.body else {}
        equipment_id = data.get('equipment_id')

        if equipment_id:
            # Categorize single equipment
            result = auto_categorize_equipment(equipment_id)
            return JsonResponse({
                'success': True,
                'result': result
            })
        else:
            # Auto-categorize all uncategorized equipment
            uncategorized = Equipment.objects.filter(category='other')
            results = []
            categorized_count = 0

            for equipment in uncategorized:
                try:
                    result = auto_categorize_equipment(equipment.id)
                    results.append({
                        'equipment_id': equipment.id,
                        'equipment_name': equipment.name,
                        'result': result
                    })

                    if result.get('confidence', 0) > 0.7:
                        categorized_count += 1

                except Exception as e:
                    logger.error(f"Error categorizing {equipment.name}: {e}")
                    continue

            return JsonResponse({
                'success': True,
                'results': results,
                'categorized': categorized_count,
                'processed': len(results)
            })

    except Exception as e:
        logger.error(f"Auto-categorization API error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@login_required
def api_image_recognition(request):
    """API endpoint for image-based asset recognition"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        if 'image' not in request.FILES:
            return JsonResponse({'error': 'No image provided'}, status=400)

        image_file = request.FILES['image']

        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp']
        if image_file.content_type not in allowed_types:
            return JsonResponse({'error': 'Invalid file type'}, status=400)

        # Validate file size (10MB limit)
        if image_file.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File too large (max 10MB)'}, status=400)

        # Save uploaded image temporarily
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            for chunk in image_file.chunks():
                temp_file.write(chunk)
            temp_image_path = temp_file.name

        try:
            # Use AI service for image recognition
            service = AssetCategorizationService()

            # For now, we'll use the text-based categorization
            # You can implement actual image recognition here
            result = {
                'category': 'other',
                'confidence': 0.3,
                'reasoning': 'Image analysis placeholder - implement actual image recognition',
                'suggestions': [
                    'Enable image-based classification with proper ML models',
                    'Train custom models on your asset images',
                    'Consider using cloud vision APIs'
                ],
                'extracted_specs': {}
            }

            # Clean up temp file
            os.unlink(temp_image_path)

            return JsonResponse({
                'success': True,
                'result': result,
                'filename': image_file.name
            })

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
            raise e

    except Exception as e:
        logger.error(f"Image recognition API error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_unread_counts(request):
    """API endpoint to get unread message and notification counts"""
    try:
        from messages.models import Message, SystemNotification
        from django.db.models import Q

        # Count unread messages
        unread_messages = Message.objects.filter(
            thread__participants=request.user
        ).exclude(read_by=request.user).exclude(sender=request.user).count()

        # Count unread notifications
        unread_notifications = SystemNotification.objects.filter(
            Q(recipients=request.user) | Q(target_roles__icontains=request.user.role),
            is_active=True
        ).count()

        return JsonResponse({
            'success': True,
            'messages': unread_messages,
            'notifications': unread_notifications
        })

    except Exception as e:
        logger.error(f"Unread counts API error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_recent_messages(request):
    """API endpoint to get recent messages for widget"""
    try:
        from messages.models import MessageThread

        # Get user's recent threads with latest messages
        threads = MessageThread.objects.filter(
            participants=request.user,
            is_archived=False
        ).order_by('-updated_at')[:5]

        messages_data = []
        for thread in threads:
            last_message = thread.last_message
            if last_message:
                messages_data.append({
                    'id': str(last_message.id),
                    'content': last_message.content,
                    'sender': {
                        'id': last_message.sender.id if last_message.sender else None,
                        'username': last_message.sender.username if last_message.sender else 'System',
                    },
                    'created_at': last_message.created_at.isoformat(),
                    'thread_id': str(thread.id)
                })

        return JsonResponse({
            'success': True,
            'messages': messages_data
        })

    except Exception as e:
        logger.error(f"Recent messages API error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def equipment_ai_analysis(request, equipment_id):
    """Detailed AI analysis page for specific equipment"""
    equipment = get_object_or_404(Equipment, id=equipment_id)

    try:
        # Run comprehensive analysis
        service = PredictiveMaintenanceService()
        health_analysis = service.analyze_equipment_health(equipment_id, days=90)

        # Run categorization analysis
        categorization_service = AssetCategorizationService()
        categorization_result = categorization_service.categorize_asset(
            name=equipment.name,
            description=equipment.specifications or "",
            manufacturer=equipment.manufacturer,
            model=equipment.model
        )

        # Get historical interventions
        interventions = Intervention.objects.filter(equipment=equipment).order_by('-created_at')[:10]

        context = {
            'equipment': equipment,
            'health_analysis': health_analysis,
            'categorization_result': categorization_result,
            'interventions': interventions,
        }

        return render(request, 'assets/ai/equipment_analysis.html', context)

    except Exception as e:
        logger.error(f"Equipment AI analysis error: {e}")
        messages.error(request, f"Error analyzing equipment: {str(e)}")
        return redirect('assets:equipment_detail', pk=equipment_id)