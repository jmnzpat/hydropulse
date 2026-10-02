"""
HydroPulse: Audit Logging Helper
Maintains tamper-evident compliance logs of user logins, record creations, updates,
deletions, threshold changes, and alert resolutions.
"""

from typing import Optional
from django.http import HttpRequest
from core.models import AuditLog


def get_client_ip(request: HttpRequest) -> str:
    """Extracts client IP address safely from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip or '127.0.0.1'


def log_audit(
    request: Optional[HttpRequest],
    action: str,
    module: str,
    record_id: str = "",
    details: str = "",
    user = None
) -> AuditLog:
    """
    Creates an immutable audit log entry.
    Supports either explicit request object or explicit user object.
    """
    actual_user = None
    ip_addr = '127.0.0.1'
    user_display = 'SYSTEM'

    if request is not None:
        ip_addr = get_client_ip(request)
        if hasattr(request, 'user') and request.user.is_authenticated:
            actual_user = request.user
            user_display = f"{request.user.username} ({request.user.get_role_display()})"
    elif user is not None and user.is_authenticated:
        actual_user = user
        user_display = f"{user.username} ({user.get_role_display()})"

    return AuditLog.objects.create(
        user=actual_user,
        user_display=user_display,
        action=action,
        module=module,
        record_id=str(record_id),
        details=details,
        ip_address=ip_addr
    )
