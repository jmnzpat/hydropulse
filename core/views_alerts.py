"""
HydroPulse: Automated Alert & Notification Views
Manages the complete alert lifecycle (New -> Acknowledged -> Resolved),
recipient registries, test notification dispatches, and notification audit logs.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q

from core.models import (
    Alert, AlertStatus, AlertSeverity, NotificationRecipient,
    NotificationLog, WaterSource
)
from core.forms_alerts import NotificationRecipientForm, AlertResolutionForm, TestNotificationForm
from core.notifications import NotificationService
from core.audit import log_audit
from core.rbac import (
    alert_management_required, admin_required,
    can_manage_alerts
)


# ========================================================
# Alert Lifecycle Management Views
# ========================================================

@login_required
def alert_list_view(request):
    """
    Surveillance alerts overview with status and severity filters.
    Accessible to all authenticated staff, with management actions for Health Officers & Admins.
    """
    status_filter = request.GET.get('status', '').strip()
    severity_filter = request.GET.get('severity', '').strip()
    barangay_filter = request.GET.get('barangay', '').strip()
    query = request.GET.get('q', '').strip()

    alerts = Alert.objects.select_related('source', 'record', 'acknowledged_by', 'resolved_by').all()

    if status_filter and status_filter in AlertStatus.values:
        alerts = alerts.filter(status=status_filter)

    if severity_filter and severity_filter in AlertSeverity.values:
        alerts = alerts.filter(severity=severity_filter)

    if barangay_filter:
        alerts = alerts.filter(source__barangay__iexact=barangay_filter)

    if query:
        alerts = alerts.filter(
            Q(summary__icontains=query) |
            Q(source__name__icontains=query) |
            Q(source__code__icontains=query)
        )

    # Status counts for badge tabs
    new_count = Alert.objects.filter(status=AlertStatus.NEW).count()
    ack_count = Alert.objects.filter(status=AlertStatus.ACKNOWLEDGED).count()
    resolved_count = Alert.objects.filter(status=AlertStatus.RESOLVED).count()

    paginator = Paginator(alerts, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    distinct_barangays = WaterSource.objects.values_list('barangay', flat=True).distinct()

    return render(request, 'alerts/alert_list.html', {
        'page_obj': page_obj,
        'new_count': new_count,
        'ack_count': ack_count,
        'resolved_count': resolved_count,
        'selected_status': status_filter,
        'selected_severity': severity_filter,
        'selected_barangay': barangay_filter,
        'query': query,
        'distinct_barangays': distinct_barangays,
        'can_manage': can_manage_alerts(request.user),
    })


@login_required
def alert_detail_view(request, alert_id):
    """
    Detailed inspection of a water contamination alert, including associated
    laboratory readings, notification transmission logs, and remediation lifecycle.
    """
    alert = get_object_or_404(
        Alert.objects.select_related('source', 'record', 'acknowledged_by', 'resolved_by'),
        id=alert_id
    )

    notifications = alert.notifications.all().order_by('-sent_at')
    resolution_form = AlertResolutionForm() if alert.status != AlertStatus.RESOLVED else None

    return render(request, 'alerts/alert_detail.html', {
        'alert': alert,
        'notifications': notifications,
        'resolution_form': resolution_form,
        'can_manage': can_manage_alerts(request.user),
    })


@alert_management_required
def alert_acknowledge_view(request, alert_id):
    """
    Health Officer or Admin acknowledges an active alert.
    Transitions alert: NEW -> ACKNOWLEDGED.
    """
    if request.method == 'POST':
        alert = get_object_or_404(Alert, id=alert_id)
        if alert.status == AlertStatus.NEW:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = request.user
            alert.acknowledged_at = timezone.now()
            alert.save()

            log_audit(
                request,
                action="ALERT_ACKNOWLEDGE",
                module="ALERTS",
                record_id=str(alert.id),
                details=f"Acknowledged {alert.severity} alert for {alert.source.name}"
            )
            messages.success(request, f"Alert for '{alert.source.name}' acknowledged.")
        else:
            messages.info(request, "This alert has already been acknowledged or resolved.")
            
    return redirect('core:alert_detail', alert_id=alert_id)


@alert_management_required
def alert_resolve_view(request, alert_id):
    """
    Health Officer or Admin records remedial actions and resolves the alert.
    Transitions alert: ACKNOWLEDGED / NEW -> RESOLVED.
    """
    alert = get_object_or_404(Alert, id=alert_id)

    if request.method == 'POST':
        form = AlertResolutionForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data['resolution_notes']
            alert.status = AlertStatus.RESOLVED
            alert.resolved_by = request.user
            alert.resolved_at = timezone.now()
            alert.resolution_notes = notes

            # If not previously acknowledged, acknowledge simultaneously
            if not alert.acknowledged_at:
                alert.acknowledged_by = request.user
                alert.acknowledged_at = timezone.now()

            alert.save()

            log_audit(
                request,
                action="ALERT_RESOLVE",
                module="ALERTS",
                record_id=str(alert.id),
                details=f"Resolved alert for {alert.source.name}. Remediation: {notes[:80]}..."
            )
            messages.success(request, f"Alert for '{alert.source.name}' has been marked as RESOLVED.")
            return redirect('core:alert_detail', alert_id=alert.id)
        else:
            messages.error(request, "Please enter detailed resolution notes describing the remediation action.")

    return redirect('core:alert_detail', alert_id=alert_id)


# ========================================================
# Notification Recipients Management Views (Admin)
# ========================================================

@admin_required
def notification_recipient_list_view(request):
    """Admin directory of registered alert recipients (Email & SMS)."""
    recipients = NotificationRecipient.objects.all().order_by('-created_at')
    is_mock = NotificationService.is_mock_mode()
    return render(request, 'alerts/recipients_list.html', {
        'recipients': recipients,
        'is_mock_mode': is_mock,
    })


@admin_required
def notification_recipient_create_view(request):
    """Admin registers a new official or technician for automated alerts."""
    if request.method == 'POST':
        form = NotificationRecipientForm(request.POST)
        if form.is_valid():
            recipient = form.save()
            log_audit(
                request,
                action="RECIPIENT_CREATE",
                module="NOTIFICATIONS",
                record_id=str(recipient.id),
                details=f"Added alert recipient {recipient.name} ({recipient.role_title})"
            )
            messages.success(request, f"Recipient '{recipient.name}' added to alert distribution list.")
            return redirect('core:notification_recipients')
    else:
        form = NotificationRecipientForm()

    return render(request, 'alerts/recipient_form.html', {
        'form': form,
        'is_edit': False,
        'title': 'Add Alert Notification Recipient'
    })


@admin_required
def notification_recipient_edit_view(request, recipient_id):
    """Admin edits contact details and channel preferences for an alert recipient."""
    recipient = get_object_or_404(NotificationRecipient, id=recipient_id)

    if request.method == 'POST':
        form = NotificationRecipientForm(request.POST, instance=recipient)
        if form.is_valid():
            form.save()
            log_audit(
                request,
                action="RECIPIENT_UPDATE",
                module="NOTIFICATIONS",
                record_id=str(recipient.id),
                details=f"Updated alert recipient {recipient.name}"
            )
            messages.success(request, f"Recipient '{recipient.name}' updated.")
            return redirect('core:notification_recipients')
    else:
        form = NotificationRecipientForm(instance=recipient)

    return render(request, 'alerts/recipient_form.html', {
        'form': form,
        'recipient': recipient,
        'is_edit': True,
        'title': f'Edit Recipient: {recipient.name}'
    })


@admin_required
def notification_recipient_toggle_view(request, recipient_id):
    """Quick toggle active status for an alert recipient."""
    if request.method == 'POST':
        recipient = get_object_or_404(NotificationRecipient, id=recipient_id)
        recipient.is_active = not recipient.is_active
        recipient.save()
        status_str = "activated" if recipient.is_active else "deactivated"
        log_audit(
            request,
            action="RECIPIENT_TOGGLE",
            module="NOTIFICATIONS",
            record_id=str(recipient.id),
            details=f"Recipient {recipient.name} {status_str}"
        )
        messages.success(request, f"Recipient '{recipient.name}' {status_str}.")
    return redirect('core:notification_recipients')


@admin_required
def notification_test_send_view(request, recipient_id):
    """Dispatches a simulated test alert to verify recipient delivery."""
    recipient = get_object_or_404(NotificationRecipient, id=recipient_id)

    if request.method == 'POST':
        form = TestNotificationForm(request.POST)
        if form.is_valid():
            channel = form.cleaned_data['channel']
            custom_msg = form.cleaned_data.get('custom_message') or "This is a simulated HydroPulse water safety test alert."
            
            dispatched = []
            if channel in ('BOTH', 'EMAIL') and recipient.email:
                subject = "[HydroPulse TEST] Emergency Alert Dispatch Verification"
                body = f"Hello {recipient.name},\n\n{custom_msg}\n\nHydroPulse Notification System is functional."
                ok = NotificationService.send_email(recipient, subject, body)
                if ok:
                    dispatched.append("Email")

            if channel in ('BOTH', 'SMS') and recipient.phone_number:
                sms_msg = f"[HydroPulse TEST] {custom_msg[:120]}"
                ok = NotificationService.send_sms(recipient, sms_msg)
                if ok:
                    dispatched.append("SMS")

            if dispatched:
                messages.success(request, f"Test notification dispatched to {recipient.name} via: {', '.join(dispatched)}.")
            else:
                messages.warning(request, "No notification sent. Please verify recipient email/phone configuration.")

            return redirect('core:notification_logs')
    else:
        form = TestNotificationForm()

    return render(request, 'alerts/test_send.html', {
        'recipient': recipient,
        'form': form
    })


# ========================================================
# Notification Transmission Audit Log View
# ========================================================

@login_required
def notification_log_list_view(request):
    """
    Displays full audit log of all SMS and Email alerts dispatched by the system.
    Shows delivery status (Sent, Failed, Mocked) and full message content.
    """
    channel_filter = request.GET.get('channel', '').strip()
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    logs = NotificationLog.objects.select_related('alert').all().order_by('-sent_at')

    if channel_filter:
        logs = logs.filter(channel=channel_filter)

    if status_filter:
        logs = logs.filter(status=status_filter)

    if query:
        logs = logs.filter(
            Q(recipient_name__icontains=query) |
            Q(destination__icontains=query) |
            Q(message_content__icontains=query)
        )

    paginator = Paginator(logs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'alerts/notification_logs.html', {
        'page_obj': page_obj,
        'channel_filter': channel_filter,
        'status_filter': status_filter,
        'query': query,
    })
