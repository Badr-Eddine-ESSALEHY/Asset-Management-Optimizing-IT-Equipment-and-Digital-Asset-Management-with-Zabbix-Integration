# messages/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import MessageThread, Message, SystemNotification
import uuid

User = get_user_model()


class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # User's personal notification group
        self.user_group_name = f"user_{self.user.id}"

        # Role-based groups for system notifications
        self.role_group_name = f"role_{self.user.role}"

        # Join user groups
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.channel_layer.group_add(
            self.role_group_name,
            self.channel_name
        )

        await self.accept()

        # Send unread message count on connect
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))

    async def disconnect(self, close_code):
        # Leave groups
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

        await self.channel_layer.group_discard(
            self.role_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'send_message':
                await self.handle_send_message(data)
            elif action == 'join_thread':
                await self.handle_join_thread(data)
            elif action == 'leave_thread':
                await self.handle_leave_thread(data)
            elif action == 'mark_read':
                await self.handle_mark_read(data)
            elif action == 'typing':
                await self.handle_typing(data)

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            await self.send_error(f"Error: {str(e)}")

    async def handle_send_message(self, data):
        thread_id = data.get('thread_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        priority = data.get('priority', 'normal')

        if not content or not thread_id:
            await self.send_error("Content and thread_id required")
            return

        # Create message in database
        message = await self.create_message(
            thread_id, content, message_type, priority
        )

        if message:
            # Get thread participants
            participants = await self.get_thread_participants(thread_id)

            # Send to all participants
            message_data = {
                'type': 'new_message',
                'message': {
                    'id': str(message.id),
                    'thread_id': str(thread_id),
                    'sender': {
                        'id': self.user.id,
                        'username': self.user.username,
                        'first_name': self.user.first_name,
                        'last_name': self.user.last_name,
                    },
                    'content': message.content,
                    'message_type': message.message_type,
                    'priority': message.priority,
                    'created_at': message.created_at.isoformat(),
                }
            }

            for participant in participants:
                await self.channel_layer.group_send(
                    f"user_{participant.id}",
                    message_data
                )

    async def handle_join_thread(self, data):
        thread_id = data.get('thread_id')
        if thread_id:
            await self.channel_layer.group_add(
                f"thread_{thread_id}",
                self.channel_name
            )

    async def handle_leave_thread(self, data):
        thread_id = data.get('thread_id')
        if thread_id:
            await self.channel_layer.group_discard(
                f"thread_{thread_id}",
                self.channel_name
            )

    async def handle_mark_read(self, data):
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_read(message_id)

    async def handle_typing(self, data):
        thread_id = data.get('thread_id')
        is_typing = data.get('is_typing', False)

        if thread_id:
            await self.channel_layer.group_send(
                f"thread_{thread_id}",
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_typing': is_typing
                }
            )

    # Message handlers for different message types
    async def new_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def system_notification(self, event):
        await self.send(text_data=json.dumps(event))

    async def typing_indicator(self, event):
        # Don't send typing indicator to the sender
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def intervention_alert(self, event):
        await self.send(text_data=json.dumps(event))

    async def asset_alert(self, event):
        await self.send(text_data=json.dumps(event))

    # Database operations
    @database_sync_to_async
    def create_message(self, thread_id, content, message_type, priority):
        try:
            thread = MessageThread.objects.get(id=thread_id)

            # Check if user is participant
            if not thread.participants.filter(id=self.user.id).exists():
                return None

            message = Message.objects.create(
                thread=thread,
                sender=self.user,
                content=content,
                message_type=message_type,
                priority=priority
            )

            # Update thread timestamp
            thread.updated_at = timezone.now()
            thread.save()

            return message
        except MessageThread.DoesNotExist:
            return None

    @database_sync_to_async
    def get_thread_participants(self, thread_id):
        try:
            thread = MessageThread.objects.get(id=thread_id)
            return list(thread.participants.all())
        except MessageThread.DoesNotExist:
            return []

    @database_sync_to_async
    def mark_message_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id)
            message.mark_as_read(self.user)
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def get_unread_count(self):
        # Get count of unread messages for this user
        from django.db.models import Q
        return Message.objects.filter(
            thread__participants=self.user
        ).exclude(
            read_by=self.user
        ).exclude(
            sender=self.user
        ).count()

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))


class SystemNotificationConsumer(AsyncWebsocketConsumer):
    """Dedicated consumer for system-wide notifications"""

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Join system notification groups
        await self.channel_layer.group_add(
            "system_notifications",
            self.channel_name
        )

        await self.channel_layer.group_add(
            f"role_{self.user.role}",
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            "system_notifications",
            self.channel_name
        )

        await self.channel_layer.group_discard(
            f"role_{self.user.role}",
            self.channel_name
        )

    async def system_alert(self, event):
        """Handle system alerts"""
        await self.send(text_data=json.dumps({
            'type': 'system_alert',
            'alert': event['alert'],
            'timestamp': timezone.now().isoformat()
        }))

    async def asset_maintenance_due(self, event):
        """Handle maintenance due alerts"""
        await self.send(text_data=json.dumps({
            'type': 'maintenance_due',
            'equipment': event['equipment'],
            'due_date': event['due_date'],
            'timestamp': timezone.now().isoformat()
        }))

    async def license_expiring(self, event):
        """Handle license expiration alerts"""
        await self.send(text_data=json.dumps({
            'type': 'license_expiring',
            'license': event['license'],
            'expiry_date': event['expiry_date'],
            'days_remaining': event['days_remaining'],
            'timestamp': timezone.now().isoformat()
        }))

    async def warranty_expiring(self, event):
        """Handle warranty expiration alerts"""
        await self.send(text_data=json.dumps({
            'type': 'warranty_expiring',
            'equipment': event['equipment'],
            'expiry_date': event['expiry_date'],
            'days_remaining': event['days_remaining'],
            'timestamp': timezone.now().isoformat()
        }))


# Utility functions to send notifications
async def send_system_notification(notification_type, data, target_users=None, target_roles=None):
    """Send system notification to specified users or roles"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    message = {
        'type': 'system_alert',
        'alert': {
            'notification_type': notification_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
    }

    # Send to specific users
    if target_users:
        for user in target_users:
            await channel_layer.group_send(f"user_{user.id}", message)

    # Send to role groups
    if target_roles:
        for role in target_roles:
            await channel_layer.group_send(f"role_{role}", message)

    # Send to all system notification listeners
    if not target_users and not target_roles:
        await channel_layer.group_send("system_notifications", message)


async def send_intervention_notification(intervention):
    """Send real-time notification for new intervention"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    # Notify admins about new intervention
    await channel_layer.group_send("role_admin", {
        'type': 'intervention_alert',
        'intervention': {
            'id': intervention.id,
            'title': intervention.title,
            'equipment': intervention.equipment.name,
            'priority': intervention.priority,
            'technician': intervention.technician.username if intervention.technician else None,
            'scheduled_date': intervention.scheduled_date.isoformat(),
        }
    })


async def send_asset_alert(equipment, alert_type, message):
    """Send asset-related alerts"""
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    # Send to admins and technicians
    for role in ['admin', 'technician']:
        await channel_layer.group_send(f"role_{role}", {
            'type': 'asset_alert',
            'equipment': {
                'id': equipment.id,
                'name': equipment.name,
                'asset_tag': equipment.asset_tag,
            },
            'alert_type': alert_type,
            'message': message,
        })