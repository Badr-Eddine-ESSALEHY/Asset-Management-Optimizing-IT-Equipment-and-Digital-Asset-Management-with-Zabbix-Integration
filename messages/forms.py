from django import forms
from django.contrib.auth import get_user_model
from .models import Message, MessageThread, SystemNotification, MessageTemplate

User = get_user_model()


class MessageForm(forms.ModelForm):
    """Form for creating new messages"""

    class Meta:
        model = Message
        fields = ['content', 'message_type', 'priority', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Type your message...',
                'class': 'form-control'
            }),
            'message_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['message_type'].initial = 'text'
        self.fields['priority'].initial = 'normal'


class ThreadForm(forms.ModelForm):
    """Form for creating new message threads"""

    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select users to include in this conversation"
    )

    class Meta:
        model = MessageThread
        fields = ['thread_type', 'title', 'participants']
        widgets = {
            'thread_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Conversation title...'
            })
        }

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if current_user:
            self.fields['participants'].queryset = User.objects.exclude(id=current_user.id).order_by('username')
        self.fields['thread_type'].initial = 'direct'


class NotificationForm(forms.ModelForm):
    """Form for system notifications (admin only)"""

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select specific users (optional)"
    )

    target_roles = forms.MultipleChoiceField(
        choices=[
            ('admin', 'Administrators'),
            ('technician', 'Technicians'),
            ('user', 'Regular Users'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select user roles to notify"
    )

    class Meta:
        model = SystemNotification
        fields = [
            'notification_type', 'title', 'message', 'recipients',
            'target_roles', 'expires_at', 'action_url', 'action_text'
        ]
        widgets = {
            'notification_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'action_url': forms.URLInput(attrs={'class': 'form-control'}),
            'action_text': forms.TextInput(attrs={'class': 'form-control'})
        }

    def clean(self):
        cleaned_data = super().clean()
        recipients = cleaned_data.get('recipients')
        target_roles = cleaned_data.get('target_roles')

        if not recipients and not target_roles:
            raise forms.ValidationError("Please select either specific recipients or target roles.")

        if target_roles:
            cleaned_data['target_roles'] = ','.join(target_roles)

        return cleaned_data


class QuickMessageForm(forms.Form):
    """Quick message form for asset-related messages"""

    recipient = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    message_type = forms.ChoiceField(
        choices=Message.MESSAGE_TYPES,
        initial='text',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        choices=Message.PRIORITY_LEVELS,
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['recipient'].queryset = User.objects.exclude(id=user.id)


class InterventionMessageForm(forms.Form):
    """Form for intervention-related communication"""

    message_type = forms.ChoiceField(
        choices=[
            ('intervention_request', 'Intervention Request'),
            ('asset_update', 'Asset Update'),
            ('text', 'General Message'),
        ],
        initial='intervention_request',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    priority = forms.ChoiceField(
        choices=Message.PRIORITY_LEVELS,
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Describe the intervention needed or provide updates...',
        }),
        help_text="Describe the intervention required, including any specific details or urgency."
    )

    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        help_text="Optional: attach images, documents, or other relevant files."
    )


class MessageTemplateForm(forms.ModelForm):
    """Form for creating message templates"""

    class Meta:
        model = MessageTemplate
        fields = [
            'name', 'template_type', 'subject_template', 'message_template', 'available_variables'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'subject_template': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Subject template (e.g., "Alert for {{user_name}}")'
            }),
            'message_template': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Message content (use {{variable}} syntax)',
            }),
            'available_variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'JSON object, e.g. {"user_name": "User Name"}',
            }),
        }


class SystemNotificationForm(NotificationForm):
    """Alias for backwards compatibility"""
    pass
