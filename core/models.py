"""
HydroPulse: Core Data Models
Implements complete database schema for Water Quality Monitoring & Management
Target SDGs: SDG 6 (Clean Water and Sanitation), SDG 3 (Good Health and Well-Being)
"""

from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'System Administrator'
    HEALTH_OFFICER = 'HEALTH_OFFICER', 'Health Officer / LGU Official'
    ENGINEER = 'ENGINEER', 'Sanitation Engineer'
    RESIDENT = 'RESIDENT', 'Resident'


class User(AbstractUser):
    """
    Custom User model with role-based attributes and contact details.
    """
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.RESIDENT,
        help_text="Role determining system permissions"
    )
    phone_number = models.CharField(max_length=25, blank=True, help_text="e.g. +63 912 345 6789")
    barangay = models.CharField(max_length=100, blank=True, help_text="Assigned or residential barangay")
    employee_id = models.CharField(max_length=50, blank=True, null=True, help_text="Official Staff/LGU ID")

    class Meta:
        ordering = ['last_name', 'first_name', 'username']

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name} ({self.get_role_display()})" if full_name else f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_health_officer(self):
        return self.role == UserRole.HEALTH_OFFICER

    @property
    def is_sanitation_engineer(self):
        return self.role == UserRole.ENGINEER

    @property
    def is_resident(self):
        return self.role == UserRole.RESIDENT

    def can_input_records(self):
        """
        Check if user can input/edit water test records.
        Default: Sanitation Engineers & Admins.
        Configurable: Health Officers can also input if setting is enabled.
        """
        if self.is_admin or self.is_sanitation_engineer:
            return True
        if self.is_health_officer:
            return SystemSetting.get_bool('ALLOW_HEALTH_OFFICER_DATA_ENTRY', default=False)
        return False


class SourceType(models.TextChoices):
    DEEP_WELL = 'DEEP_WELL', 'Communal Deep Well'
    SHALLOW_WELL = 'SHALLOW_WELL', 'Shallow Tube Well'
    SPRING = 'SPRING', 'Natural Spring Box'
    COMMUNAL_TAP = 'COMMUNAL_TAP', 'Public Communal Tap Stand'
    REFILLING_STATION = 'REFILLING_STATION', 'Local Water Refilling Station'


class WaterSource(models.Model):
    """
    Represents communal wells, stations, taps, or springs monitored by HydroPulse.
    """
    code = models.CharField(max_length=50, unique=True, help_text="Unique source identifier, e.g., WELL-BARANGAY-01")
    name = models.CharField(max_length=150, help_text="Descriptive name (e.g., Purok 3 Communal Well)")
    source_type = models.CharField(max_length=30, choices=SourceType.choices, default=SourceType.DEEP_WELL)
    barangay = models.CharField(max_length=100, help_text="Barangay / village name")
    address_details = models.TextField(blank=True, help_text="Landmark or exact location notes")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text="Optional GPS Latitude")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text="Optional GPS Longitude")
    is_active = models.BooleanField(default=True, help_text="Active for regular water sampling")
    assigned_engineer = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_sources',
        limit_choices_to={'role': UserRole.ENGINEER},
        help_text="Sanitation Engineer assigned to monitor this source"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['barangay', 'name']
        indexes = [
            models.Index(fields=['barangay', 'is_active']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.name} [{self.code}] - Brgy. {self.barangay}"

    @property
    def latest_record(self):
        return self.records.filter(is_deleted=False).order_by('-tested_at').first()

    @property
    def current_status(self):
        latest = self.latest_record
        return latest.overall_status if latest else 'UNTESTED'


class SafetyThreshold(models.Model):
    """
    Water quality parameter safety thresholds.
    Configurable by System Administrator; based on PNSDW 2017 & WHO guidelines.
    """
    parameter_code = models.CharField(max_length=30, unique=True, help_text="Identifier: 'ph', 'turbidity', 'tds'")
    parameter_name = models.CharField(max_length=100, help_text="Display name: e.g. 'pH Level'")
    unit = models.CharField(max_length=20, help_text="Measurement unit (e.g., pH, NTU, mg/L)")
    min_safe = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Lower limit (inclusive)")
    max_safe = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Upper limit (inclusive)")
    caution_margin_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Percentage proximity to limit that triggers CAUTION status (e.g. 10%)"
    )
    standard_reference = models.CharField(max_length=150, default="PNSDW 2017 / WHO Guidelines")
    description = models.TextField(blank=True, help_text="Health effects or significance of this parameter")
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['parameter_code']

    def __str__(self):
        return f"{self.parameter_name} ({self.min_safe or '-'} to {self.max_safe or '-'} {self.unit})"


class WaterQualityStatus(models.TextChoices):
    SAFE = 'SAFE', 'Safe'
    CAUTION = 'CAUTION', 'Caution'
    UNSAFE = 'UNSAFE', 'Unsafe'


class WaterQualityRecord(models.Model):
    """
    Individual water quality test reading for a water source.
    Includes soft-deletion and automated evaluation results.
    """
    source = models.ForeignKey(WaterSource, on_delete=models.CASCADE, related_name='records')
    tested_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='tested_records')
    tested_at = models.DateTimeField(help_text="Date and time water sample was tested")
    
    # Core Parameters
    ph_level = models.DecimalField(max_digits=5, decimal_places=2, help_text="pH Level (0.00 - 14.00)")
    turbidity_ntu = models.DecimalField(max_digits=7, decimal_places=2, help_text="Turbidity in Nephelometric Turbidity Units (NTU)")
    tds_ppm = models.DecimalField(max_digits=8, decimal_places=2, help_text="Total Dissolved Solids in mg/L (ppm)")
    
    # Automated Safety Evaluation Result
    overall_status = models.CharField(
        max_length=15,
        choices=WaterQualityStatus.choices,
        default=WaterQualityStatus.SAFE,
        help_text="Calculated overall safety status"
    )
    failed_parameters = models.JSONField(
        default=list,
        blank=True,
        help_text="List of parameter codes and explanations that violated safe or caution limits"
    )
    notes = models.TextField(blank=True, help_text="Field technician notes, weather conditions, or observations")
    
    # Soft Delete Support
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='deleted_records')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-tested_at']
        indexes = [
            models.Index(fields=['source', 'tested_at']),
            models.Index(fields=['overall_status', 'is_deleted']),
        ]

    def __str__(self):
        return f"{self.source.name} - {self.tested_at.strftime('%Y-%m-%d')} ({self.overall_status})"


class AlertStatus(models.TextChoices):
    NEW = 'NEW', 'New'
    ACKNOWLEDGED = 'ACKNOWLEDGED', 'Acknowledged'
    RESOLVED = 'RESOLVED', 'Resolved'


class AlertSeverity(models.TextChoices):
    WARNING = 'WARNING', 'Warning (Caution Level)'
    CRITICAL = 'CRITICAL', 'Critical (Unsafe Contamination)'


class Alert(models.Model):
    """
    Automated alert generated whenever a water quality test is evaluated as UNSAFE or CAUTION.
    Maintains full lifecycle: New -> Acknowledged -> Resolved.
    """
    record = models.ForeignKey(WaterQualityRecord, on_delete=models.CASCADE, related_name='alerts')
    source = models.ForeignKey(WaterSource, on_delete=models.CASCADE, related_name='alerts')
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.NEW)
    severity = models.CharField(max_length=20, choices=AlertSeverity.choices, default=AlertSeverity.CRITICAL)
    summary = models.TextField(help_text="Summary of violated water parameters")
    
    # Lifecycle Tracking
    acknowledged_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, help_text="Actions taken to remediate water source (e.g. shock chlorination, re-testing)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['source', 'status']),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.source.name} - {self.status}"


class NotificationRecipient(models.Model):
    """
    Registered recipients (officials, engineers, LGU leaders) who receive automated email/SMS alerts.
    """
    name = models.CharField(max_length=150)
    role_title = models.CharField(max_length=100, help_text="e.g. Municipal Health Officer, Barangay Kagawad")
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=25, blank=True, help_text="Format: +639123456789")
    barangay_filter = models.CharField(
        max_length=100,
        blank=True,
        help_text="Barangay name to filter alerts for, or leave blank to receive alerts for all barangays"
    )
    receive_email = models.BooleanField(default=True)
    receive_sms = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.role_title})"


class NotificationLog(models.Model):
    """
    Audit log of all SMS and Email notifications dispatched by HydroPulse.
    """
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
    ]
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('MOCKED', 'Simulated (Mock/Console Mode)'),
    ]

    alert = models.ForeignKey(Alert, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')
    recipient_name = models.CharField(max_length=150)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    destination = models.CharField(max_length=150, help_text="Email address or phone number")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    message_content = models.TextField()
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.channel} to {self.destination} [{self.status}]"


class AdvisoryType(models.TextChoices):
    BOIL_WATER = 'BOIL_WATER', 'Boil Water Advisory'
    CONTAMINATION_ALERT = 'CONTAMINATION_ALERT', 'Water Contamination Warning'
    MAINTENANCE = 'MAINTENANCE', 'System Maintenance & Flushing'
    CLEARANCE = 'CLEARANCE', 'Safety Clearance / Advisory Lifted'


class Advisory(models.Model):
    """
    Public safety bulletins published by Health Officers / LGU officials for community awareness.
    Exposed on the Public Safety Portal without revealing staff internal data.
    """
    title = models.CharField(max_length=200, help_text="e.g. Boil Water Notice for Purok 2 Residents")
    advisory_type = models.CharField(max_length=30, choices=AdvisoryType.choices, default=AdvisoryType.BOIL_WATER)
    barangay = models.CharField(max_length=100, blank=True, help_text="Specific barangay or leave blank for municipality-wide")
    affected_sources = models.ManyToManyField(WaterSource, blank=True, related_name='advisories')
    summary = models.TextField(help_text="Plain language description of the water quality advisory")
    instructions = models.TextField(
        help_text="Actionable instructions for residents (e.g. boil water for at least 3 minutes, use designated alternate station)"
    )
    is_active = models.BooleanField(default=True, help_text="Visible on the public portal")
    published_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='published_advisories')
    published_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiration date/time")

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.get_advisory_type_display()}: {self.title}"


class AuditLog(models.Model):
    """
    Security and audit compliance trail tracking critical system actions:
    User logins, test record creation/updates/deletions, threshold changes, and alert resolutions.
    """
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    user_display = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=100, help_text="e.g. USER_LOGIN, RECORD_CREATE, THRESHOLD_UPDATE")
    module = models.CharField(max_length=50, help_text="e.g. AUTH, WATER_RECORDS, THRESHOLDS, ALERTS")
    record_id = models.CharField(max_length=64, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['module', 'action']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.user_display}: {self.action} ({self.module})"


class SystemSetting(models.Model):
    """
    Global key-value configuration for system operational flags and behavior.
    Allows Admin to toggle permissions, notification modes, and tolerances without redeployment.
    """
    DATA_TYPE_CHOICES = [
        ('STRING', 'String'),
        ('BOOLEAN', 'Boolean'),
        ('INTEGER', 'Integer'),
        ('FLOAT', 'Float'),
    ]

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=255)
    data_type = models.CharField(max_length=10, choices=DATA_TYPE_CHOICES, default='STRING')

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get_val(cls, key, default=None):
        try:
            item = cls.objects.get(key=key)
            if item.data_type == 'BOOLEAN' or item.value.strip().lower() in ('true', 'false', '0', '1'):
                return item.value.strip().lower() in ('true', '1', 'yes', 't', 'enabled')
            elif item.data_type == 'INTEGER':
                return int(item.value)
            elif item.data_type == 'FLOAT':
                return float(item.value)
            return item.value
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_bool(cls, key, default=False):
        val = cls.get_val(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ('true', '1', 'yes', 't', 'enabled')
        return bool(val)

    @classmethod
    def set_val(cls, key, value, description=""):
        obj, _ = cls.objects.get_or_create(key=key, defaults={'description': description})
        if isinstance(value, bool):
            obj.data_type = 'BOOLEAN'
            obj.value = 'True' if value else 'False'
        else:
            str_val = str(value)
            if str_val.strip().lower() in ('true', 'false'):
                obj.data_type = 'BOOLEAN'
            obj.value = str_val
        if description:
            obj.description = description
        obj.save()
        return obj
