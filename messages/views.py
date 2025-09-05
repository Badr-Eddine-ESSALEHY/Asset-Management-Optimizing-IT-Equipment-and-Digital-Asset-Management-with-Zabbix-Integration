# messages/views.py
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import MessageForm, ThreadForm, NotificationForm
from .models import MessageThread, Message, SystemNotification

User = get_user_model()


@login_required
def messaging_dashboard(request):
    """Main messaging dashboard"""
    user = request.user

    # Get user's threads with latest message info
    threads = MessageThread.objects.filter(
        participants=user,
        is_archived=False
    ).annotate(
        last_message_time=Max('messages__created_at'),
        unread_count=Count('messages', filter=~Q(messages__read_by=user))
    ).order_by('-last_message_time')[:10]

    # Get recent system notifications
    notifications = SystemNotification.objects.filter(
        Q(recipients=user) | Q(target_roles__icontains=user.role),
        is_active=True
    ).order_by('-created_at')[:10]

    # Get unread message count
    unread_total = Message.objects.filter(
        thread__participants=user
    ).exclude(read_by=user).exclude(sender=user).count()

    context = {
        'threads': threads,
        'notifications': notifications,
        'unread_total': unread_total,
        'user_role': user.role,
    }

    return render(request, 'messages/dashboard.html', context)


@login_required
def thread_detail(request, thread_id):
    """View individual message thread"""
    thread = get_object_or_404(MessageThread, id=thread_id)

    # Check if user is participant
    if not thread.participants.filter(id=request.user.id).exists():
        messages.error(request, "You don't have access to this conversation.")
        return redirect('messages:dashboard')

    # Get messages with pagination
    thread_messages = thread.messages.select_related('sender').order_by('created_at')
    paginator = Paginator(thread_messages, 50)
    page = request.GET.get('page', 1)
    messages_page = paginator.get_page(page)

    # Mark messages as read
    unread_messages = thread.messages.exclude(read_by=request.user)
    for message in unread_messages:
        message.mark_as_read(request.user)

    # Handle new message form
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.thread = thread
            message.sender = request.user
            message.save()

            # Send real-time notification
            send_message_notification(message)

            return redirect('messages:thread_detail', thread_id=thread.id)
    else:
        form = MessageForm()

    context = {
        'thread': thread,
        'messages': messages_page,
        'form': form,
        'participants': thread.participants.all(),
    }

    return render(request, 'messages/thread_detail.html', context)


@login_required
def create_thread(request):
    """Create a new message thread"""
    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.created_by = request.user
            thread.save()

            # Add creator as participant
            thread.participants.add(request.user)

            # Add selected participants
            participants = form.cleaned_data.get('participants')
            if participants:
                thread.participants.add(*participants)

            messages.success(request, f'Conversation "{thread.title}" created successfully.')
            return redirect('messages:thread_detail', thread_id=thread.id)
    else:
        form = ThreadForm()

    # Get users for participant selection
    users = User.objects.exclude(id=request.user.id).order_by('username')

    context = {
        'form': form,
        'users': users,
    }

    return render(request, 'messages/create_thread.html', context)


@login_required
def system_notifications(request):
    """View system notifications"""
    user = request.user

    # Get notifications for user
    notifications = SystemNotification.objects.filter(
        Q(recipients=user) | Q(target_roles__icontains=user.role),
        is_active=True
    ).order_by('-created_at')

    # Pagination
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page)

    context = {
        'notifications': notifications_page,
    }

    return render(request, 'messages/notifications.html', context)


@login_required
def send_intervention_message(request, intervention_id):
    """Send message about an intervention"""
    from assets.models import Intervention

    intervention = get_object_or_404(Intervention, id=intervention_id)

    # Create or get thread for this intervention
    thread, created = MessageThread.objects.get_or_create(
        related_intervention=intervention,
        defaults={
            'thread_type': 'intervention',
            'title': f'Intervention: {intervention.title}',
            'created_by': request.user,
        }
    )

    # Add relevant participants
    if created:
        thread.participants.add(request.user)
        if intervention.technician:
            thread.participants.add(intervention.technician)

        # Add admins
        admins = User.objects.filter(role='admin')
        thread.participants.add(*admins)

    return redirect('messages:thread_detail', thread_id=thread.id)


@login_required
def send_equipment_message(request, equipment_id):
    """Send message about equipment"""
    from assets.models import Equipment

    equipment = get_object_or_404(Equipment, id=equipment_id)

    # Create or get thread for this equipment
    thread, created = MessageThread.objects.get_or_create(
        related_equipment=equipment,
        defaults={
            'thread_type': 'group',
            'title': f'Equipment: {equipment.name}',
            'created_by': request.user,
        }
    )

    # Add relevant participants
    if created:
        thread.participants.add(request.user)
        if equipment.assigned_to:
            thread.participants.add(equipment.assigned_to)

        # Add admins and technicians
        staff = User.objects.filter(role__in=['admin', 'technician'])
        thread.participants.add(*staff)

    return redirect('messages:thread_detail', thread_id=thread.id)


# API Views for AJAX/WebSocket integration

@login_required
def api_user_search(request):
    """Search users for thread participants"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id=request.user.id)[:10]

    users_data = [{
        'id': user.id,
        'username': user.username,
        'name': f"{user.first_name} {user.last_name}".strip(),
        'role': user.role,
    } for user in users]

    return JsonResponse({'users': users_data})


@login_required
def api_thread_messages(request, thread_id):
    """Get messages for a thread (AJAX)"""
    thread = get_object_or_404(MessageThread, id=thread_id)

    # Check access
    if not thread.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    # Get messages
    messages_qs = thread.messages.select_related('sender').order_by('-created_at')

    # Pagination
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))

    paginator = Paginator(messages_qs, per_page)
    messages_page = paginator.get_page(page)

    messages_data = []
    for message in messages_page:
        messages_data.append({
            'id': str(message.id),
            'content': message.content,
            'sender': {
                'id': message.sender.id if message.sender else None,
                'username': message.sender.username if message.sender else 'System',
                'name': f"{message.sender.first_name} {message.sender.last_name}".strip() if message.sender else 'System',
            },
            'message_type': message.message_type,
            'priority': message.priority,
            'created_at': message.created_at.isoformat(),
            'is_system': message.is_system_message,
        })

    return JsonResponse({
        'messages': messages_data,
        'has_next': messages_page.has_next(),
        'has_previous': messages_page.has_previous(),
        'page': page,
        'total_pages': paginator.num_pages,
    })


@login_required
def api_mark_read(request, message_id):
    """Mark message as read"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    message = get_object_or_404(Message, id=message_id)

    # Check if user is participant in thread
    if not message.thread.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    message.mark_as_read(request.user)

    return JsonResponse({'success': True})


# Admin Views

class SystemNotificationCreateView(LoginRequiredMixin, CreateView):
    """Admin view to create system notifications"""
    model = SystemNotification
    form_class = NotificationForm
    template_name = 'messages/admin/create_notification.html'
    success_url = reverse_lazy('messages:admin_notifications')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.role == 'admin':
            messages.error(request, "Only admins can create system notifications.")
            return redirect('messages:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)

        # Send real-time notification
        send_system_notification_broadcast(self.object)

        messages.success(self.request, "System notification sent successfully.")
        return response


@login_required
def admin_notifications(request):
    """Admin view for managing notifications"""
    if request.user.role != 'admin':
        messages.error(request, "Access denied.")
        return redirect('messages:dashboard')

    notifications = SystemNotification.objects.all().order_by('-created_at')
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page)

    context = {
        'notifications': notifications_page,
    }

    return render(request, 'messages/admin/notifications.html', context)


# Utility functions

def send_message_notification(message):
    """Send real-time notification for new message"""
    channel_layer = get_channel_layer()

    # Get thread participants except sender
    participants = message.thread.participants.exclude(id=message.sender.id if message.sender else None)

    message_data = {
        'type': 'new_message',
        'message': {
            'id': str(message.id),
            'thread_id': str(message.thread.id),
            'sender': {
                'id': message.sender.id if message.sender else None,
                'username': message.sender.username if message.sender else 'System',
            },
            'content': message.content,
            'message_type': message.message_type,
            'priority': message.priority,
            'created_at': message.created_at.isoformat(),
        }
    }

    # Send to each participant
    for participant in participants:
        async_to_sync(channel_layer.group_send)(
            f"user_{participant.id}",
            message_data
        )


def send_system_notification_broadcast(notification):
    """Send system notification to all target users"""
    channel_layer = get_channel_layer()

    notification_data = {
        'type': 'system_notification',
        'notification': {
            'id': str(notification.id),
            'title': notification.title,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'created_at': notification.created_at.isoformat(),
            'action_url': notification.action_url,
            'action_text': notification.action_text,
        }
    }

    # Get target users
    target_users = notification.get_target_users()

    # Send to each target user
    for user in target_users:
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            notification_data
        )
@login_required
def api_mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    notification = get_object_or_404(SystemNotification, id=notification_id)

    # Check if user should have access to this notification
    if not notification.recipients.filter(id=request.user.id).exists() and \
            not (notification.target_roles and request.user.role in notification.target_roles.split(',')):
        return JsonResponse({'error': 'Access denied'}, status=403)

    notification.is_read = True
    notification.save()

    return JsonResponse({'success': True})


@login_required
def api_mark_all_notifications_read(request):
    """Mark all notifications as read for current user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    notifications = SystemNotification.objects.filter(
        Q(recipients=request.user) | Q(target_roles__icontains=request.user.role),
        is_active=True,
        is_read=False
    )

    notifications.update(is_read=True)

    return JsonResponse({'success': True, 'marked_count': notifications.count()})