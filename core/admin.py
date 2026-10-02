"""
HydroPulse: Django Admin Registration
Provides back-office management for staff and administrators.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from core.models import (
    User, WaterSource, SafetyThreshold, WaterQualityRecord,
    Alert, NotificationRecipient, NotificationLog, Advisory,
    AuditLog, SystemSetting
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'barangay', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'barangay')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('HydroPulse RBAC & Profile', {'fields': ('role', 'phone_number', 'barangay', 'employee_id')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('HydroPulse RBAC & Profile', {'fields': ('role', 'phone_number', 'barangay', 'employee_id')}),
    )


@admin.register(WaterSource)
class WaterSourceAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'source_type', 'barangay', 'is_active', 'assigned_engineer', 'current_status')
    list_filter = ('source_type', 'barangay', 'is_active')
    search_fields = ('code', 'name', 'barangay', 'address_details')


@admin.register(SafetyThreshold)
class SafetyThresholdAdmin(admin.ModelAdmin):
    list_display = ('parameter_code', 'parameter_name', 'min_safe', 'max_safe', 'unit', 'caution_margin_percent', 'standard_reference')


@admin.register(WaterQualityRecord)
class WaterQualityRecordAdmin(admin.ModelAdmin):
    list_display = ('source', 'tested_at', 'overall_status', 'ph_level', 'turbidity_ntu', 'tds_ppm', 'tested_by', 'is_deleted')
    list_filter = ('overall_status', 'is_deleted', 'source__barangay')
    search_fields = ('source__name', 'source__code', 'notes')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('source', 'severity', 'status', 'created_at', 'acknowledged_by', 'resolved_by')
    list_filter = ('status', 'severity')


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ('name', 'role_title', 'email', 'phone_number', 'barangay_filter', 'is_active')


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_name', 'channel', 'destination', 'status', 'sent_at')
    list_filter = ('channel', 'status')


@admin.register(Advisory)
class AdvisoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'advisory_type', 'barangay', 'is_active', 'published_at', 'published_by')
    list_filter = ('advisory_type', 'is_active', 'barangay')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user_display', 'module', 'action', 'ip_address')
    list_filter = ('module', 'action')
    search_fields = ('user_display', 'details', 'ip_address')
    readonly_fields = ('timestamp', 'user', 'user_display', 'action', 'module', 'record_id', 'details', 'ip_address')


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'data_type', 'description')
