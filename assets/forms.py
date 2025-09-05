# assets/forms.py
from .models import  Software, License, Intervention
from django import forms
from assets.models import Equipment

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = '__all__'
        widgets = {
            # These widgets correctly specify the HTML input type
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_expiration': forms.DateInput(attrs={'type': 'date'}),
            'last_seen': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

class SoftwareForm(forms.ModelForm):
    class Meta:
        model = Software
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

class LicenseForm(forms.ModelForm):
    class Meta:
        model = License
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

class InterventionForm(forms.ModelForm):
    class Meta:
        model = Intervention
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})


class MonitoringSetupForm(forms.ModelForm):
    """Form for setting up monitoring on equipment"""

    class Meta:
        model = Equipment
        fields = ['monitoring_enabled', 'ip_address', 'hostname']
        widgets = {
            'monitoring_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.1.100'}),
            'hostname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'server-01'}),
        }

    def clean_ip_address(self):
        ip_address = self.cleaned_data.get('ip_address')
        monitoring_enabled = self.cleaned_data.get('monitoring_enabled')

        if monitoring_enabled and not ip_address:
            raise forms.ValidationError('IP address is required when monitoring is enabled.')

        # Basic IP validation
        if ip_address:
            try:
                import ipaddress
                ipaddress.ip_address(ip_address)
            except ValueError:
                raise forms.ValidationError('Please enter a valid IP address.')