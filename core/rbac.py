"""
HydroPulse: Role-Based Access Control (RBAC) Module
Defines permission verification functions and view decorators.
Enforces the principle of least privilege across all routes.
"""

from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from core.models import UserRole, SystemSetting


def get_user_role(user):
    """Safely retrieves the role of the user, defaulting to RESIDENT if anonymous."""
    if not user.is_authenticated:
        return UserRole.RESIDENT
    return getattr(user, 'role', UserRole.RESIDENT)


def is_admin(user) -> bool:
    return user.is_authenticated and (user.role == UserRole.ADMIN or user.is_superuser)


def is_health_officer(user) -> bool:
    return user.is_authenticated and user.role == UserRole.HEALTH_OFFICER


def is_sanitation_engineer(user) -> bool:
    return user.is_authenticated and user.role == UserRole.ENGINEER


def is_resident(user) -> bool:
    return not user.is_authenticated or user.role == UserRole.RESIDENT


def can_input_records(user) -> bool:
    """
    Evaluates whether the user has permission to encode or update water quality test records.
    - System Administrators: Always allowed.
    - Sanitation Engineers: Always allowed.
    - Health Officers: Allowed IF 'ALLOW_HEALTH_OFFICER_DATA_ENTRY' setting is True.
    - Residents / Anonymous: Not allowed.
    """
    if not user.is_authenticated:
        return False
    if is_admin(user) or is_sanitation_engineer(user):
        return True
    if is_health_officer(user):
        return SystemSetting.get_bool('ALLOW_HEALTH_OFFICER_DATA_ENTRY', default=False)
    return False


def can_manage_sources(user) -> bool:
    """Admin and Sanitation Engineers can manage water source entities."""
    return is_admin(user) or is_sanitation_engineer(user)


def can_manage_alerts(user) -> bool:
    """Health Officers and Admins can acknowledge and resolve alerts."""
    return is_admin(user) or is_health_officer(user)


def can_publish_advisories(user) -> bool:
    """Health Officers and Admins can author and publish public advisories."""
    return is_admin(user) or is_health_officer(user)


def can_generate_reports(user) -> bool:
    """Health Officers, Admins, and Engineers can generate formal summaries."""
    return is_admin(user) or is_health_officer(user) or is_sanitation_engineer(user)


def can_manage_thresholds(user) -> bool:
    """Only Admins can modify safety thresholds in accordance with PNSDW/WHO."""
    return is_admin(user)


def can_manage_users(user) -> bool:
    """Only Admins can register, activate/deactivate, and assign user roles."""
    return is_admin(user)


# ==========================================
# View Decorators
# ==========================================

def role_required(*allowed_roles):
    """
    Decorator for views that checks if the logged-in user belongs to any of the allowed roles.
    Redirects with a warning message if unauthorized.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please log in to access this feature.")
                return redirect(f"{reverse('core:login')}?next={request.path}")
            
            if request.user.role in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "Access Denied: Your account role does not have permission to view this page.")
            return redirect('core:dashboard')
        return _wrapped_view
    return decorator


def admin_required(view_func):
    """Decorator requiring System Administrator privileges."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Administrator login required.")
            return redirect(f"{reverse('core:login')}?next={request.path}")
        if is_admin(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to System Administrators only.")
        return redirect('core:dashboard')
    return _wrapped_view


def record_entry_required(view_func):
    """Decorator checking permission to encode test records (takes config toggle into account)."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to encode water quality records.")
            return redirect(f"{reverse('core:login')}?next={request.path}")
        if can_input_records(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, "You do not have authorization to encode or edit water quality test records.")
        return redirect('core:dashboard')
    return _wrapped_view


def alert_management_required(view_func):
    """Decorator requiring Health Officer or Admin privileges for alert handling."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('core:login')}?next={request.path}")
        if can_manage_alerts(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Only Health Officers and Administrators can manage alert lifecycle.")
        return redirect('core:dashboard')
    return _wrapped_view
