from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Profile
import re

CustomUser = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """Enhanced user creation form with better validation and styling"""

    DEPARTMENT_CHOICES = [
        ('', 'Select Department'),
        ('IT', 'Information Technology'),
        ('HR', 'Human Resources'),
        ('Finance', 'Finance'),
        ('Operations', 'Operations'),
        ('Marketing', 'Marketing'),
        ('Sales', 'Sales'),
        ('Support', 'Customer Support'),
        ('Other', 'Other'),
    ]

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your email address'
        }),
        help_text='We\'ll use this email for important notifications.'
    )

    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your first name'
        })
    )

    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your last name'
        })
    )

    department = forms.ChoiceField(
        choices=DEPARTMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': '+1 (555) 123-4567'
        }),
        help_text='Format: +1 (555) 123-4567'
    )

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'department',
            'phone',
            'password1',
            'password2'
        ]
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Choose a unique username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Enhanced styling for password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Create a strong password'
        })

        self.fields['password2'].widget.attrs.update({
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Confirm your password'
        })

    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if email:
            if CustomUser.objects.filter(email__iexact=email).exists():
                raise ValidationError("A user with this email already exists.")
        return email.lower()

    def clean_phone(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove all non-digit characters for validation
            digits_only = re.sub(r'\D', '', phone)
            if len(digits_only) < 10 or len(digits_only) > 15:
                raise ValidationError("Please enter a valid phone number (10-15 digits).")
        return phone

    def clean_username(self):
        """Enhanced username validation"""
        username = self.cleaned_data.get('username')
        if username:
            # Check for special characters (only allow letters, numbers, underscore, hyphen)
            if not re.match(r'^[\w\-]+$', username):
                raise ValidationError("Username can only contain letters, numbers, underscores, and hyphens.")

            # Check minimum length
            if len(username) < 3:
                raise ValidationError("Username must be at least 3 characters long.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False  # All new users are non-staff by default
        user.role = 'user'
        user.department = self.cleaned_data.get('department', '')
        user.phone = self.cleaned_data.get('phone', '')

        if commit:
            user.save()
            # Create profile - this is now handled by the signal, but we keep it for safety
            Profile.objects.get_or_create(user=user)

        return user


class UserUpdateForm(forms.ModelForm):
    """Enhanced user update form"""

    DEPARTMENT_CHOICES = [
        ('', 'Select Department'),
        ('IT', 'Information Technology'),
        ('HR', 'Human Resources'),
        ('Finance', 'Finance'),
        ('Operations', 'Operations'),
        ('Marketing', 'Marketing'),
        ('Sales', 'Sales'),
        ('Support', 'Customer Support'),
        ('Other', 'Other'),
    ]

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

    department = forms.ChoiceField(
        choices=DEPARTMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'department', 'phone']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': '+1 (555) 123-4567'
            }),
        }

    def clean_email(self):
        """Validate email uniqueness (excluding current user)"""
        email = self.cleaned_data.get('email')
        if email:
            # Exclude current user from uniqueness check
            existing_user = CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if existing_user.exists():
                raise ValidationError("A user with this email already exists.")
        return email.lower()

    def clean_phone(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone')
        if phone:
            digits_only = re.sub(r'\D', '', phone)
            if len(digits_only) < 10 or len(digits_only) > 15:
                raise ValidationError("Please enter a valid phone number (10-15 digits).")
        return phone


class ProfileUpdateForm(forms.ModelForm):
    """Enhanced profile update form with all profile fields"""

    class Meta:
        model = Profile
        fields = ['profile_picture', 'bio', 'location', 'website']
        widgets = {
            'profile_picture': forms.ClearableFileInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'accept': 'image/*'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Tell us about yourself...',
                'rows': 4
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'City, Country'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'https://yourwebsite.com'
            })
        }

    def clean_profile_picture(self):
        """Validate profile picture"""
        picture = self.cleaned_data.get('profile_picture')

        if picture:
            # Only validate if a new file was uploaded (has content_type attribute)
            if hasattr(picture, 'content_type'):
                # Check file size (max 2MB)
                if picture.size > 2 * 1024 * 1024:
                    raise ValidationError("Image file too large. Maximum size is 2MB.")

                # Check file type
                if not picture.content_type.startswith('image/'):
                    raise ValidationError("Please upload a valid image file.")

                # Check image dimensions
                from PIL import Image
                try:
                    img = Image.open(picture)
                    width, height = img.size

                    # Maximum dimensions
                    if width > 2000 or height > 2000:
                        raise ValidationError("Image dimensions too large. Maximum size is 2000x2000 pixels.")

                    # Reset file pointer
                    picture.seek(0)

                except Exception:
                    raise ValidationError("Invalid image file.")

        return picture

    def clean_bio(self):
        """Validate bio length"""
        bio = self.cleaned_data.get('bio')
        if bio and len(bio) > 500:
            raise ValidationError("Bio must be 500 characters or less.")
        return bio


class BulkUserActionForm(forms.Form):
    """Form for bulk user actions"""

    ACTION_CHOICES = [
        ('activate', 'Activate Users'),
        ('deactivate', 'Deactivate Users'),
        ('delete', 'Delete Users'),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )

    user_ids = forms.CharField(
        widget=forms.HiddenInput()
    )

    def clean_user_ids(self):
        """Validate user IDs"""
        user_ids = self.cleaned_data.get('user_ids')
        if user_ids:
            try:
                ids = [int(id.strip()) for id in user_ids.split(',') if id.strip()]
                if not ids:
                    raise ValidationError("No users selected.")
                return ids
            except ValueError:
                raise ValidationError("Invalid user selection.")
        raise ValidationError("No users selected.")


class UserSearchForm(forms.Form):
    """Form for user search functionality"""

    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Search by username, email, or name...'
        })
    )

    role = forms.ChoiceField(
        choices=[
            ('', 'All Roles'),
            ('admin', 'Administrators'),
            ('user', 'Users'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

    status = forms.ChoiceField(
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

    department = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Filter by department'
        })
    )


class EnhancedPasswordChangeForm(PasswordChangeForm):
    """Enhanced password change form with better styling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            })

        self.fields['old_password'].widget.attrs['placeholder'] = 'Enter your current password'
        self.fields['new_password1'].widget.attrs['placeholder'] = 'Enter your new password'
        self.fields['new_password2'].widget.attrs['placeholder'] = 'Confirm your new password'


class AccountPreferencesForm(forms.Form):
    """Form for user account preferences"""

    email_notifications = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox h-5 w-5 text-green-600 transition duration-150 ease-in-out'
        }),
        label="Receive email notifications"
    )

    profile_visibility = forms.ChoiceField(
        choices=[
            ('public', 'Public - Visible to everyone'),
            ('team', 'Team - Visible to team members only'),
            ('private', 'Private - Only visible to you'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        }),
        initial='team'
    )

    two_factor_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox h-5 w-5 text-green-600 transition duration-150 ease-in-out'
        }),
        label="Enable two-factor authentication"
    )