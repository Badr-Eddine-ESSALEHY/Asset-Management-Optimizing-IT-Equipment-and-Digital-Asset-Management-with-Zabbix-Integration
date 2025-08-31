# assets/forms.py
from django import forms
from .models import Equipment, Software, License, Intervention, Location


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