"""
HydroPulse: Global Context Processors
Injects user roles, permissions, system settings, and pending alerts into all templates.
"""

from core.models import UserRole, Alert, Advisory, SystemSetting
from core import rbac


def hydropulse_context(request):
    """
    Context processor adding global HydroPulse helpers to all rendered templates.
    """
    user = request.user
    role = rbac.get_user_role(user)

    can_input = rbac.can_input_records(user)
    can_alerts = rbac.can_manage_alerts(user)
    can_sources = rbac.can_manage_sources(user)
    can_reports = rbac.can_generate_reports(user)
    can_admin = rbac.is_admin(user)

    pending_alerts_count = 0
    active_advisories_count = 0
    try:
        pending_alerts_count = Alert.objects.filter(status='NEW').count()
        active_advisories_count = Advisory.objects.filter(is_active=True).count()
    except Exception:
        pass

    allow_health_officer_entry = SystemSetting.get_bool('ALLOW_HEALTH_OFFICER_DATA_ENTRY', default=False)

    return {
        'CURRENT_ROLE': role,
        'UserRole': UserRole,
        'CAN_INPUT_RECORDS': can_input,
        'CAN_MANAGE_ALERTS': can_alerts,
        'CAN_MANAGE_SOURCES': can_sources,
        'CAN_GENERATE_REPORTS': can_reports,
        'IS_SYSTEM_ADMIN': can_admin,
        'PENDING_ALERTS_COUNT': pending_alerts_count,
        'ACTIVE_ADVISORIES_COUNT': active_advisories_count,
        'ALLOW_HEALTH_OFFICER_DATA_ENTRY': allow_health_officer_entry,
    }
