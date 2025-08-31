from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, Profile


class RecentLoginFilter(SimpleListFilter):
    """Filter users by recent login activity"""
    title = 'Recent Login Activity'
    parameter_name = 'recent_login'

    def lookups(self, request, model_admin):
        return (
            ('7days', 'Last 7 days'),
            ('30days', 'Last 30 days'),
            ('never', 'Never logged in'),
            ('inactive', 'Inactive for 30+ days'),
        )

    def queryset(self, request, queryset):
        if self.value() == '7days':
            return queryset.filter(last_login__gte=timezone.now() - timedelta(days=7))
        elif self.value() == '30days':
            return queryset.filter(last_login__gte=timezone.now() - timedelta(days=30))
        elif self.value() == 'never':
            return queryset.filter(last_login__isnull=True)
        elif self.value() == 'inactive':
            return queryset.filter(last_login__lt=timezone.now() - timedelta(days=30))


class DepartmentFilter(SimpleListFilter):
    """Filter users by department"""
    title = 'Department'
    parameter_name = 'department'

    def lookups(self, request, model_admin):
        departments = CustomUser.objects.values_list('department', flat=True).distinct()
        return [(dept, dept) for dept in departments if dept]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department=self.value())


class ProfileInline(admin.StackedInline):
    """Inline admin for user profiles"""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fields = ('profile_picture', 'bio', 'location', 'website')
    extra = 0


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Enhanced admin interface for CustomUser"""

    model = CustomUser
    inlines = [ProfileInline]

    # List display configuration
    list_display = (
        'username_with_avatar',
        'email',
        'full_name',
        'department_badge',
        'role_badge',
        'status_indicator',
        'login_info',
        'date_joined_short',
        'quick_actions'
    )

    # Filters
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        DepartmentFilter,
        RecentLoginFilter,
        'date_joined',
    )

    # Search configuration
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'department',
        'phone'
    )

    # Ordering
    ordering = ('-date_joined',)

    # List per page
    list_per_page = 25

    # Actions
    actions = ['activate_users', 'deactivate_users', 'make_staff', 'remove_staff']

    # Field organization
    fieldsets = (
        ('Account Information', {
            'fields': ('username', 'password', 'email')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone', 'department'),
            'classes': ('collapse',)
        }),
        ('Permissions & Role', {
            'fields': (
                'role',
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            ),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('Create New User', {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'first_name',
                'last_name',
                'department',
                'phone',
                'password1',
                'password2',
                'is_staff',
                'is_active'
            )
        }),
    )

    # Custom display methods
    def username_with_avatar(self, obj):
        """Display username with avatar"""
        if hasattr(obj, 'profile') and obj.profile.profile_picture:
            return format_html(
                '<div style="display: flex; align-items: center;">'
                '<img src="{}" style="width: 30px; height: 30px; border-radius: 50%; margin-right: 10px; object-fit: cover;">'
                '<strong>{}</strong>'
                '</div>',
                obj.profile.profile_picture.url,
                obj.username
            )
        else:
            return format_html(
                '<div style="display: flex; align-items: center;">'
                '<div style="width: 30px; height: 30px; border-radius: 50%; margin-right: 10px; background: #e5e7eb; display: flex; align-items: center; justify-content: center; color: #6b7280; font-size: 12px;">'
                '{}'
                '</div>'
                '<strong>{}</strong>'
                '</div>',
                obj.username[0].upper() if obj.username else '?',
                obj.username
            )

    username_with_avatar.short_description = 'User'
    username_with_avatar.admin_order_field = 'username'

    def full_name(self, obj):
        """Display user's full name"""
        name = obj.get_full_name()
        return name if name else format_html('<em style="color: #6b7280;">Not provided</em>')

    full_name.short_description = 'Full Name'
    full_name.admin_order_field = 'first_name'

    def department_badge(self, obj):
        """Display department as a badge"""
        if obj.department:
            return format_html(
                '<span style="background: #dbeafe; color: #1e40af; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">'
                '{}'
                '</span>',
                obj.department
            )
        return format_html('<span style="color: #6b7280;">—</span>')

    department_badge.short_description = 'Department'
    department_badge.admin_order_field = 'department'

    def role_badge(self, obj):
        """Display user role as a colored badge"""
        if obj.is_superuser:
            return format_html(
                '<span style="background: #fee2e2; color: #991b1b; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">'
                '⚡ SUPER ADMIN'
                '</span>'
            )
        elif obj.is_staff:
            return format_html(
                '<span style="background: #e0e7ff; color: #3730a3; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">'
                '👑 ADMIN'
                '</span>'
            )
        else:
            return format_html(
                '<span style="background: #f3f4f6; color: #374151; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">'
                '👤 USER'
                '</span>'
            )

    role_badge.short_description = 'Role'
    role_badge.admin_order_field = 'is_staff'

    def status_indicator(self, obj):
        """Display user status with visual indicator"""
        if obj.is_active:
            return format_html(
                '<span style="display: flex; align-items: center;">'
                '<span style="width: 8px; height: 8px; background: #10b981; border-radius: 50%; margin-right: 6px;"></span>'
                '<span style="color: #065f46; font-weight: 500;">Active</span>'
                '</span>'
            )
        else:
            return format_html(
                '<span style="display: flex; align-items: center;">'
                '<span style="width: 8px; height: 8px; background: #ef4444; border-radius: 50%; margin-right: 6px;"></span>'
                '<span style="color: #991b1b; font-weight: 500;">Inactive</span>'
                '</span>'
            )

    status_indicator.short_description = 'Status'
    status_indicator.admin_order_field = 'is_active'

    def login_info(self, obj):
        """Display last login information"""
        if obj.last_login:
            time_since = timezone.now() - obj.last_login
            if time_since.days == 0:
                return format_html(
                    '<span style="color: #059669; font-weight: 500;">Today</span><br>'
                    '<span style="color: #6b7280; font-size: 11px;">{}</span>',
                    obj.last_login.strftime('%H:%M')
                )
            elif time_since.days < 7:
                return format_html(
                    '<span style="color: #0891b2;">{} days ago</span>',
                    time_since.days
                )
            else:
                return format_html(
                    '<span style="color: #6b7280;">{}</span>',
                    obj.last_login.strftime('%b %d, %Y')
                )
        else:
            return format_html('<span style="color: #ef4444;">Never</span>')

    login_info.short_description = 'Last Login'
    login_info.admin_order_field = 'last_login'

    def date_joined_short(self, obj):
        """Display join date in short format"""
        return format_html(
            '<span title="{}">{}</span>',
            obj.date_joined.strftime('%B %d, %Y at %H:%M'),
            obj.date_joined.strftime('%b %d, %Y')
        )

    date_joined_short.short_description = 'Joined'
    date_joined_short.admin_order_field = 'date_joined'

    def quick_actions(self, obj):
        """Display quick action buttons"""
        actions = []

        # Edit button
        edit_url = reverse('admin:members_customuser_change', args=[obj.pk])
        actions.append(
            f'<a href="{edit_url}" style="background: #3b82f6; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; margin-right: 4px;" title="Edit user">✏️</a>'
        )

        # Toggle status button
        if obj.is_active:
            actions.append(
                f'<a href="#" onclick="toggleUserStatus({obj.pk}, false)" style="background: #f59e0b; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; margin-right: 4px;" title="Deactivate user">⏸️</a>'
            )
        else:
            actions.append(
                f'<a href="#" onclick="toggleUserStatus({obj.pk}, true)" style="background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; margin-right: 4px;" title="Activate user">▶️</a>'
            )

        # Delete button (only for non-staff users)
        if not obj.is_staff or obj == self.request.user:
            delete_url = reverse('admin:members_customuser_delete', args=[obj.pk])
            actions.append(
                f'<a href="{delete_url}" style="background: #ef4444; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px;" title="Delete user" onclick="return confirm(\'Are you sure?\')">🗑️</a>'
            )

        return format_html(''.join(actions))

    quick_actions.short_description = 'Actions'

    # Custom actions
    def activate_users(self, request, queryset):
        """Bulk activate users"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated} user(s) have been activated.',
            level='SUCCESS'
        )

    activate_users.short_description = "Activate selected users"

    def deactivate_users(self, request, queryset):
        """Bulk deactivate users"""
        # Don't deactivate superusers or current user
        queryset = queryset.exclude(is_superuser=True).exclude(pk=request.user.pk)
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated} user(s) have been deactivated.',
            level='SUCCESS'
        )

    deactivate_users.short_description = "Deactivate selected users"

    def make_staff(self, request, queryset):
        """Bulk promote users to staff"""
        updated = queryset.update(is_staff=True)
        self.message_user(
            request,
            f'{updated} user(s) have been promoted to staff.',
            level='SUCCESS'
        )

    make_staff.short_description = "Promote to staff"

    def remove_staff(self, request, queryset):
        """Bulk remove staff privileges"""
        # Don't demote superusers or current user
        queryset = queryset.exclude(is_superuser=True).exclude(pk=request.user.pk)
        updated = queryset.update(is_staff=False)
        self.message_user(
            request,
            f'{updated} user(s) have been demoted from staff.',
            level='SUCCESS'
        )

    remove_staff.short_description = "Remove staff privileges"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('profile')

    def changelist_view(self, request, extra_context=None):
        """Add extra context to changelist view"""
        extra_context = extra_context or {}

        # Add statistics
        queryset = self.get_queryset(request)
        extra_context['stats'] = {
            'total_users': queryset.count(),
            'active_users': queryset.filter(is_active=True).count(),
            'staff_users': queryset.filter(is_staff=True).count(),
            'recent_signups': queryset.filter(
                date_joined__gte=timezone.now() - timedelta(days=7)
            ).count(),
        }

        return super().changelist_view(request, extra_context)

    class Media:
        """Add custom CSS and JavaScript"""
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/custom_admin.js',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin interface for user profiles"""

    # Now includes all the fields that exist in the updated Profile model
    list_display = ('user', 'user_email', 'profile_picture_preview', 'bio_preview', 'created_at')
    search_fields = ('user__username', 'user__email', 'bio', 'location')

    # Now using the actual timestamp fields from the model
    list_filter = ('created_at', 'updated_at', 'user__is_active')
    readonly_fields = ('created_at', 'updated_at')

    def user_email(self, obj):
        """Display user email"""
        return obj.user.email

    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'

    def profile_picture_preview(self, obj):
        """Display profile picture thumbnail"""
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover;" />',
                obj.profile_picture.url
            )
        return "No image"

    profile_picture_preview.short_description = 'Picture'

    def bio_preview(self, obj):
        """Display truncated bio"""
        if obj.bio:
            return obj.bio[:50] + '...' if len(obj.bio) > 50 else obj.bio
        return "No bio"

    bio_preview.short_description = 'Bio'


# Customize admin site headers
admin.site.site_header = "User Management System"
admin.site.site_title = "User Admin"
admin.site.index_title = "Welcome to User Management System"