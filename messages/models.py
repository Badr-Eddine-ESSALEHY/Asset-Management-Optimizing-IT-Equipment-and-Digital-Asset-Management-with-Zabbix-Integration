# messages/models.py
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
import uuid


class MessageThread(models.Model):
    """Conversation thread between users"""
    THREAD_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('announcement', 'Announcement'),
        ('system', 'System Notification'),
        ('intervention', 'Intervention Request'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread_type = models.CharField(max_length=20, choices=THREAD_TYPES, default='direct')
    title = models.CharField(max_length=200, blank=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='message_threads'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_threads'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    # Asset-related threads
    related_equipment = models.ForeignKey(
        'assets.Equipment',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='message_threads'
    )
    related_intervention = models.ForeignKey(
        'assets.Intervention',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='message_threads'
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.get_thread_type_display()}: {self.title or 'Untitled'}"

    def get_absolute_url(self):
        return reverse('messages:thread_detail', kwargs={'thread_id': self.id})

    @property
    def last_message(self):
        return self.messages.first()  # Due to ordering

    @property
    def unread_count_for_user(self, user):
        return self.messages.filter(
            read_by__lt=models.F('created_at')
        ).exclude(sender=user).count()


class Message(models.Model):
    """Individual message within a thread"""
    MESSAGE_TYPES = [
        ('text', 'Text Message'),
        ('system', 'System Alert'),
        ('file', 'File Attachment'),
        ('asset_update', 'Asset Update'),
        ('intervention_request', 'Intervention Request'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        MessageThread,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,  # Can be null for system messages
        related_name='sent_messages'
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')

    # Content
    content = models.TextField()
    attachment = models.FileField(upload_to='message_attachments/', null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_system_message = models.BooleanField(default=False)

    # Read tracking
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='MessageRead',
        related_name='read_messages'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['thread', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['message_type', 'priority']),
        ]

    def __str__(self):
        sender_name = self.sender.username if self.sender else "System"
        return f"{sender_name}: {self.content[:50]}..."

    def mark_as_read(self, user):
        """Mark message as read by a specific user"""
        MessageRead.objects.get_or_create(
            message=self,
            user=user,
            defaults={'read_at': timezone.now()}
        )


class MessageRead(models.Model):
    """Tracking when messages are read by users"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')


class SystemNotification(models.Model):
    """System-generated notifications and alerts"""
    is_read = models.BooleanField(default=False)
    NOTIFICATION_TYPES = [
        ('asset_alert', 'Asset Alert'),
        ('maintenance_due', 'Maintenance Due'),
        ('license_expiring', 'License Expiring'),
        ('warranty_expiring', 'Warranty Expiring'),
        ('intervention_created', 'Intervention Created'),
        ('intervention_updated', 'Intervention Updated'),
        ('equipment_assigned', 'Equipment Assigned'),
        ('system_update', 'System Update'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()

    # Targeting
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='notifications'
    )
    target_roles = models.CharField(
        max_length=100,
        blank=True,
        help_text="Comma-separated roles: admin,technician,user"
    )

    # Related objects
    related_equipment = models.ForeignKey(
        'assets.Equipment',
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    related_intervention = models.ForeignKey(
        'assets.Intervention',
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    related_license = models.ForeignKey(
        'assets.License',
        on_delete=models.CASCADE,
        null=True, blank=True
    )

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Actions
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['is_active', '-created_at']),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title}"

    def get_target_users(self):
        """Get all users who should receive this notification"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users = set(self.recipients.all())

        if self.target_roles:
            roles = [role.strip() for role in self.target_roles.split(',')]
            role_users = User.objects.filter(role__in=roles)
            users.update(role_users)

        return list(users)


class MessageTemplate(models.Model):
    """Templates for common messages"""
    TEMPLATE_TYPES = [
        ('intervention_request', 'Intervention Request'),
        ('asset_assignment', 'Asset Assignment'),
        ('maintenance_reminder', 'Maintenance Reminder'),
        ('system_alert', 'System Alert'),
    ]

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    subject_template = models.CharField(max_length=200)
    message_template = models.TextField()
    is_active = models.BooleanField(default=True)

    # Variables that can be used in templates
    available_variables = models.JSONField(
        default=dict,
        help_text="JSON object of available template variables"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def render_message(self, context):
        """Render the template with given context variables"""
        import re

        # Simple template rendering - replace {{variable}} with context values
        message = self.message_template
        subject = self.subject_template

        for key, value in context.items():
            pattern = f"{{{{{key}}}}}"
            message = message.replace(pattern, str(value))
            subject = subject.replace(pattern, str(value))

        return subject, message