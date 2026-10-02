"""
HydroPulse: Authentication & User Administration Views
Implements secure login/logout, profile management, RBAC user administration,
system settings, and audit compliance logging.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import User, UserRole, SystemSetting, AuditLog
from core.forms_auth import HydroPulseLoginForm, UserCreateForm, UserEditForm, UserProfileForm, SystemSettingsForm
from core.audit import log_audit
from core.rbac import admin_required


def login_view(request):
    """Handles user authentication with audit logging."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = HydroPulseLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, "This account has been deactivated. Please contact your System Administrator.")
                return render(request, 'auth/login.html', {'form': form})
            
            login(request, user)
            log_audit(request, action="USER_LOGIN", module="AUTH", details=f"Logged in as {user.role}")
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            
            next_url = request.GET.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('core:dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = HydroPulseLoginForm(request)

    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    """Signs out user and redirects to the Public Safety Portal."""
    if request.user.is_authenticated:
        log_audit(request, action="USER_LOGOUT", module="AUTH", details="User signed out")
        logout(request)
        messages.info(request, "You have been successfully signed out.")
    return redirect('core:public_portal')


@login_required
def profile_view(request):
    """User profile overview and self-update."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            log_audit(request, action="PROFILE_UPDATE", module="AUTH", details="User updated their profile information")
            messages.success(request, "Your profile details have been updated.")
            return redirect('core:profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'auth/profile.html', {'form': form})


@login_required
def password_change_view(request):
    """Secure password change with session preservation and audit tracking."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Prevent session invalidation
            log_audit(request, action="PASSWORD_CHANGE", module="AUTH", details="User changed their password")
            messages.success(request, "Your password was successfully updated!")
            return redirect('core:profile')
        else:
            messages.error(request, "Please correct the errors indicated below.")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'auth/password_change.html', {'form': form})


# ========================================================
# Administrator User & Role Management Views
# ========================================================

@admin_required
def user_list_view(request):
    """Lists system users with role filtering, search, and status indicators."""
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()

    users = User.objects.all().order_by('-date_joined')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(barangay__icontains=query)
        )

    if role_filter and role_filter in UserRole.values:
        users = users.filter(role=role_filter)

    paginator = Paginator(users, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'auth/user_list.html', {
        'page_obj': page_obj,
        'query': query,
        'role_filter': role_filter,
        'roles': UserRole.choices,
    })


@admin_required
def user_create_view(request):
    """Administrator creates a new user account and assigns RBAC role."""
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            log_audit(
                request,
                action="USER_CREATE",
                module="USER_MANAGEMENT",
                record_id=str(new_user.id),
                details=f"Created user {new_user.username} with role {new_user.role}"
            )
            messages.success(request, f"User account '{new_user.username}' created successfully.")
            return redirect('core:user_list')
    else:
        form = UserCreateForm()

    return render(request, 'auth/user_form.html', {
        'form': form,
        'is_edit': False,
        'title': 'Register New System User'
    })


@admin_required
def user_edit_view(request, user_id):
    """Administrator edits role, contact information, and active status for a user."""
    target_user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            form.save()
            log_audit(
                request,
                action="USER_UPDATE",
                module="USER_MANAGEMENT",
                record_id=str(target_user.id),
                details=f"Updated details for user {target_user.username} (Role: {target_user.role})"
            )
            messages.success(request, f"Account for {target_user.username} updated.")
            return redirect('core:user_list')
    else:
        form = UserEditForm(instance=target_user)

    return render(request, 'auth/user_form.html', {
        'form': form,
        'target_user': target_user,
        'is_edit': True,
        'title': f'Edit User: {target_user.username}'
    })


@admin_required
def user_toggle_status_view(request, user_id):
    """Quickly toggles active/inactive state of a user account."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        if target_user == request.user:
            messages.error(request, "You cannot deactivate your own administrative account.")
            return redirect('core:user_list')

        target_user.is_active = not target_user.is_active
        target_user.save()
        status_str = "activated" if target_user.is_active else "deactivated"
        log_audit(
            request,
            action="USER_STATUS_TOGGLE",
            module="USER_MANAGEMENT",
            record_id=str(target_user.id),
            details=f"User {target_user.username} was {status_str}"
        )
        messages.success(request, f"Account '{target_user.username}' has been {status_str}.")
    return redirect('core:user_list')


# ========================================================
# Administrator System Settings & Audit Log Views
# ========================================================

@admin_required
def system_settings_view(request):
    """Allows Administrator to configure system permissions, thresholds margin, and mock mode."""
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST)
        if form.is_valid():
            allow_entry = form.cleaned_data['allow_health_officer_data_entry']
            margin = form.cleaned_data['caution_margin_percent']
            mock_mode = form.cleaned_data['notification_mock_mode']

            SystemSetting.set_val(
                'ALLOW_HEALTH_OFFICER_DATA_ENTRY',
                'True' if allow_entry else 'False',
                'Allow Health Officers to input & edit test records'
            )
            SystemSetting.set_val(
                'CAUTION_MARGIN_PERCENT',
                str(margin),
                'Proximity margin percentage for CAUTION status'
            )
            SystemSetting.set_val(
                'NOTIFICATION_MOCK_MODE',
                'True' if mock_mode else 'False',
                'Simulate email and SMS alerts without sending live external messages'
            )

            log_audit(
                request,
                action="SYSTEM_SETTINGS_UPDATE",
                module="SYSTEM_CONFIG",
                details=f"Updated settings: HealthOfficerEntry={allow_entry}, Margin={margin}%, MockMode={mock_mode}"
            )
            messages.success(request, "System settings successfully saved and applied.")
            return redirect('core:system_settings')
    else:
        initial_data = {
            'allow_health_officer_data_entry': SystemSetting.get_bool('ALLOW_HEALTH_OFFICER_DATA_ENTRY', default=False),
            'caution_margin_percent': float(SystemSetting.get_val('CAUTION_MARGIN_PERCENT', default='10.0')),
            'notification_mock_mode': SystemSetting.get_bool('NOTIFICATION_MOCK_MODE', default=True),
        }
        form = SystemSettingsForm(initial=initial_data)

    return render(request, 'core/system_settings.html', {'form': form})


@admin_required
def audit_logs_view(request):
    """Compliance audit trail viewer."""
    action_filter = request.GET.get('action', '').strip()
    module_filter = request.GET.get('module', '').strip()
    query = request.GET.get('q', '').strip()

    logs = AuditLog.objects.all().order_by('-timestamp')

    if module_filter:
        logs = logs.filter(module=module_filter)
    if action_filter:
        logs = logs.filter(action=action_filter)
    if query:
        logs = logs.filter(
            Q(details__icontains=query) |
            Q(user_display__icontains=query) |
            Q(ip_address__icontains=query)
        )

    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    distinct_modules = AuditLog.objects.values_list('module', flat=True).distinct()

    return render(request, 'core/audit_logs.html', {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'module_filter': module_filter,
        'query': query,
        'distinct_modules': distinct_modules,
    })
