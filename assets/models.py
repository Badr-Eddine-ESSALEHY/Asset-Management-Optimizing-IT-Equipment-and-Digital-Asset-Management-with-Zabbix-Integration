from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.urls import reverse

class Location(models.Model):
    """Physical location where equipment is stored or used"""
    name = models.CharField(max_length=150, unique=True)
    building = models.CharField(max_length=100, blank=True)
    floor = models.CharField(max_length=50, blank=True)
    room = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Location"
        verbose_name_plural = "Locations"

    def __str__(self):
        return f"{self.name} ({self.building or 'No Building'})"

    def get_absolute_url(self):
        return reverse('location_detail', kwargs={'pk': self.pk})


class Equipment(models.Model):
    """IT Equipment and physical assets"""
    EQUIPMENT_CATEGORIES = [
        ('desktop', 'Desktop Computer'),
        ('laptop', 'Laptop'),
        ('server', 'Server'),
        ('network', 'Network Device'),
        ('printer', 'Printer'),
        ('scanner', 'Scanner'),
        ('monitor', 'Monitor'),
        ('ups', 'UPS'),
        ('peripheral', 'Peripheral Device'),
        ('other', 'Other Equipment'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Maintenance'),
        ('retired', 'Retired'),
        ('lost', 'Lost/Stolen'),
    ]

    # Core Identification
    asset_tag = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique asset identification tag"
    )
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )
    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20,
        choices=EQUIPMENT_CATEGORIES,
        default='desktop'
    )

    # Hardware Details
    manufacturer = models.CharField(max_length=150, blank=True)
    model = models.CharField(max_length=150, blank=True)
    specifications = models.TextField(blank=True, help_text="Technical specifications")

    # Network Information
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    hostname = models.CharField(max_length=100, blank=True)

    # Status Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    condition = models.CharField(
        max_length=100,
        blank=True,
        help_text="Physical condition notes"
    )

    # Financial Information
    purchase_date = models.DateField(blank=True, null=True)
    purchase_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)]
    )
    warranty_expiration = models.DateField(blank=True, null=True)
    purchase_order = models.CharField(max_length=50, blank=True)
    supplier = models.CharField(max_length=150, blank=True)

    # Location and Assignment
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_equipment'
    )
    assigned_date = models.DateField(blank=True, null=True)

    # Monitoring and Maintenance
    monitoring_enabled = models.BooleanField(default=False)
    zabbix_hostid = models.CharField(max_length=100, blank=True, null=True)
    last_maintenance = models.DateField(blank=True, null=True)
    next_maintenance = models.DateField(blank=True, null=True)

    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_equipment'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"
        indexes = [
            models.Index(fields=['asset_tag']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.asset_tag})"

    def get_absolute_url(self):
        return reverse('equipment_detail', kwargs={'pk': self.pk})

    @property
    def age(self):
        """Return equipment age in years"""
        if self.purchase_date:
            from datetime import date
            return date.today().year - self.purchase_date.year
        return None


class Software(models.Model):
    """Software applications and systems"""
    LICENSE_TYPES = [
        ('perpetual', 'Perpetual'),
        ('subscription', 'Subscription'),
        ('open_source', 'Open Source'),
        ('trial', 'Trial'),
    ]

    name = models.CharField(max_length=200)
    vendor = models.CharField(max_length=150, blank=True)
    version = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    license_type = models.CharField(
        max_length=20,
        choices=LICENSE_TYPES,
        default='subscription'
    )
    minimum_requirements = models.TextField(blank=True)
    is_cloud = models.BooleanField(default=False)
    url = models.URLField(blank=True)
    support_contact = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Software"

    def __str__(self):
        return f"{self.name} {self.version or ''}".strip()

    def get_absolute_url(self):
        return reverse('software_detail', kwargs={'pk': self.pk})


class License(models.Model):
    """Software licenses and subscriptions"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('unassigned', 'Unassigned'),
        ('suspended', 'Suspended'),
    ]

    software = models.ForeignKey(
        Software,
        on_delete=models.CASCADE,
        related_name='licenses'
    )
    license_key = models.CharField(max_length=300)
    seats = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    purchase_date = models.DateField(blank=True, null=True)
    expiration_date = models.DateField(blank=True, null=True)
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    order_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='licenses'
    )
    installed_on = models.ForeignKey(
        Equipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installed_licenses'
    )

    class Meta:
        ordering = ['software__name', 'expiration_date']
        verbose_name_plural = "Licenses"

    def __str__(self):
        return f"{self.software.name} License ({self.license_key[:8]}...)"

    def get_absolute_url(self):
        return reverse('license_detail', kwargs={'pk': self.pk})

    @property
    def is_expired(self):
        """Check if license is expired"""
        from django.utils.timezone import localdate
        return (self.expiration_date and
                self.expiration_date < localdate() and
                self.status != 'expired')


class Intervention(models.Model):
    """Maintenance and service interventions"""
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    title = models.CharField(max_length=200)
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name='interventions'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    scheduled_date = models.DateTimeField()
    completed_date = models.DateTimeField(blank=True, null=True)
    description = models.TextField()
    resolution = models.TextField(blank=True)
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='interventions'
    )
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    parts_used = models.TextField(blank=True)
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    requires_followup = models.BooleanField(default=False)
    followup_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = "Intervention"
        verbose_name_plural = "Interventions"

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse('intervention_detail', kwargs={'pk': self.pk})

    @property
    def is_overdue(self):
        """Check if intervention is overdue"""
        from django.utils.timezone import now
        return (self.status == 'planned' and
                self.scheduled_date < now())