"""
HydroPulse: Water Sources, Test Records, and Safety Threshold Views
Implements full CRUD, soft-deletion, real-time safety evaluation, and audit logging.
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse

from core.models import (
    WaterSource, SourceType, WaterQualityRecord,
    WaterQualityStatus, SafetyThreshold, Alert, AlertSeverity,
    AlertStatus, UserRole
)
from core.forms_water import WaterSourceForm, WaterQualityRecordForm, SafetyThresholdForm
from core.safety_engine import evaluate_water_safety, get_thresholds_from_db
from core.audit import log_audit
from core.notifications import NotificationService
from core.rbac import (
    admin_required, record_entry_required,
    role_required, can_input_records, can_manage_sources
)


# ========================================================
# Water Source Management Views
# ========================================================

@login_required
def source_list_view(request):
    """Lists water sources with search, barangay, and type filters."""
    query = request.GET.get('q', '').strip()
    source_type = request.GET.get('type', '').strip()
    barangay = request.GET.get('barangay', '').strip()
    status_filter = request.GET.get('status', '').strip()

    sources = WaterSource.objects.select_related('assigned_engineer').all()

    if query:
        sources = sources.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(address_details__icontains=query)
        )

    if source_type and source_type in SourceType.values:
        sources = sources.filter(source_type=source_type)

    if barangay:
        sources = sources.filter(barangay__iexact=barangay)

    # Filter by current status if requested
    if status_filter:
        valid_pks = []
        for s in sources:
            if s.current_status == status_filter:
                valid_pks.append(s.pk)
        sources = sources.filter(pk__in=valid_pks)

    paginator = Paginator(sources, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    distinct_barangays = WaterSource.objects.values_list('barangay', flat=True).distinct()

    return render(request, 'sources/source_list.html', {
        'page_obj': page_obj,
        'query': query,
        'selected_type': source_type,
        'selected_barangay': barangay,
        'selected_status': status_filter,
        'source_types': SourceType.choices,
        'distinct_barangays': distinct_barangays,
    })


@login_required
def source_detail_view(request, source_id):
    """Detailed profile of a water source, test history, and parameter trends."""
    source = get_object_or_404(WaterSource.objects.select_related('assigned_engineer'), id=source_id)
    
    # Active records
    records = source.records.filter(is_deleted=False).order_by('-tested_at')
    
    # Recent alerts
    recent_alerts = source.alerts.order_by('-created_at')[:5]

    # Data for recent 10 tests trend chart
    recent_records_asc = list(records[:10])
    recent_records_asc.reverse()
    
    chart_dates = [r.tested_at.strftime('%b %d') for r in recent_records_asc]
    chart_ph = [float(r.ph_level) for r in recent_records_asc]
    chart_turbidity = [float(r.turbidity_ntu) for r in recent_records_asc]
    chart_tds = [float(r.tds_ppm) for r in recent_records_asc]

    paginator = Paginator(records, 10)
    page_number = request.GET.get('page')
    records_page = paginator.get_page(page_number)

    return render(request, 'sources/source_detail.html', {
        'source': source,
        'records_page': records_page,
        'recent_alerts': recent_alerts,
        'chart_dates': chart_dates,
        'chart_ph': chart_ph,
        'chart_turbidity': chart_turbidity,
        'chart_tds': chart_tds,
        'total_tests_count': records.count(),
        'safe_tests_count': records.filter(overall_status='SAFE').count(),
        'caution_tests_count': records.filter(overall_status='CAUTION').count(),
        'unsafe_tests_count': records.filter(overall_status='UNSAFE').count(),
    })


@login_required
def source_create_view(request):
    """Sanitation Engineers & Admins create water source entries."""
    if not can_manage_sources(request.user):
        messages.error(request, "Permission denied: Only Sanitation Engineers and Administrators can manage water sources.")
        return redirect('core:source_list')

    if request.method == 'POST':
        form = WaterSourceForm(request.POST)
        if form.is_valid():
            source = form.save()
            log_audit(
                request,
                action="SOURCE_CREATE",
                module="WATER_SOURCES",
                record_id=str(source.id),
                details=f"Created water source {source.name} [{source.code}] in Brgy. {source.barangay}"
            )
            messages.success(request, f"Water source '{source.name}' successfully registered.")
            return redirect('core:source_detail', source_id=source.id)
    else:
        # Pre-select logged-in user if they are Sanitation Engineer
        initial = {}
        if request.user.role == UserRole.ENGINEER:
            initial['assigned_engineer'] = request.user
        form = WaterSourceForm(initial=initial)

    return render(request, 'sources/source_form.html', {
        'form': form,
        'is_edit': False,
        'title': 'Register New Water Source'
    })


@login_required
def source_edit_view(request, source_id):
    """Sanitation Engineers & Admins edit water source entries."""
    if not can_manage_sources(request.user):
        messages.error(request, "Permission denied: Only Sanitation Engineers and Administrators can edit water sources.")
        return redirect('core:source_list')

    source = get_object_or_404(WaterSource, id=source_id)

    if request.method == 'POST':
        form = WaterSourceForm(request.POST, instance=source)
        if form.is_valid():
            form.save()
            log_audit(
                request,
                action="SOURCE_UPDATE",
                module="WATER_SOURCES",
                record_id=str(source.id),
                details=f"Updated water source {source.name} [{source.code}]"
            )
            messages.success(request, f"Water source '{source.name}' updated successfully.")
            return redirect('core:source_detail', source_id=source.id)
    else:
        form = WaterSourceForm(instance=source)

    return render(request, 'sources/source_form.html', {
        'form': form,
        'source': source,
        'is_edit': True,
        'title': f'Edit Source: {source.name}'
    })


@login_required
def source_toggle_status_view(request, source_id):
    """Quick toggle active/inactive for regular water sampling."""
    if not can_manage_sources(request.user):
        messages.error(request, "Permission denied.")
        return redirect('core:source_list')

    if request.method == 'POST':
        source = get_object_or_404(WaterSource, id=source_id)
        source.is_active = not source.is_active
        source.save()
        status_str = "activated for sampling" if source.is_active else "deactivated (sampling suspended)"
        log_audit(
            request,
            action="SOURCE_STATUS_TOGGLE",
            module="WATER_SOURCES",
            record_id=str(source.id),
            details=f"Source {source.name} was {status_str}"
        )
        messages.success(request, f"Source '{source.name}' was {status_str}.")
    return redirect('core:source_detail', source_id=source_id)


# ========================================================
# Water Quality Records Management Views
# ========================================================

@login_required
def record_list_view(request):
    """Lists test results with filtering by source, barangay, status, and date range."""
    source_id = request.GET.get('source', '').strip()
    barangay = request.GET.get('barangay', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    show_deleted = request.GET.get('show_deleted', '') == '1' and request.user.is_admin

    records = WaterQualityRecord.objects.select_related('source', 'tested_by').all()

    if not show_deleted:
        records = records.filter(is_deleted=False)

    if source_id:
        records = records.filter(source_id=source_id)

    if barangay:
        records = records.filter(source__barangay__iexact=barangay)

    if status_filter and status_filter in WaterQualityStatus.values:
        records = records.filter(overall_status=status_filter)

    if date_from:
        records = records.filter(tested_at__date__gte=date_from)

    if date_to:
        records = records.filter(tested_at__date__lte=date_to)

    paginator = Paginator(records, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    sources = WaterSource.objects.filter(is_active=True).order_by('name')
    distinct_barangays = WaterSource.objects.values_list('barangay', flat=True).distinct()

    return render(request, 'records/record_list.html', {
        'page_obj': page_obj,
        'sources': sources,
        'distinct_barangays': distinct_barangays,
        'selected_source': source_id,
        'selected_barangay': barangay,
        'selected_status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'show_deleted': show_deleted,
        'statuses': WaterQualityStatus.choices,
    })


@login_required
def record_detail_view(request, record_id):
    """Detailed view of a water test reading with parameter standards comparison."""
    record = get_object_or_404(
        WaterQualityRecord.objects.select_related('source', 'tested_by', 'deleted_by'),
        id=record_id
    )

    thresholds = get_thresholds_from_db()
    # Re-evaluate to get comprehensive threshold breakdown
    eval_result = evaluate_water_safety(
        ph=record.ph_level,
        turbidity=record.turbidity_ntu,
        tds=record.tds_ppm,
        thresholds=thresholds
    )

    associated_alerts = record.alerts.all()

    return render(request, 'records/record_detail.html', {
        'record': record,
        'eval_result': eval_result,
        'associated_alerts': associated_alerts,
        'thresholds': thresholds,
    })


@record_entry_required
def record_create_view(request):
    """Encodes new water quality test data, evaluates safety, triggers alerts."""
    source_preselect = request.GET.get('source')

    if request.method == 'POST':
        form = WaterQualityRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.tested_by = request.user

            # Real-time automated safety evaluation
            thresholds = get_thresholds_from_db()
            eval_result = evaluate_water_safety(
                ph=record.ph_level,
                turbidity=record.turbidity_ntu,
                tds=record.tds_ppm,
                thresholds=thresholds
            )

            record.overall_status = eval_result['overall_status']
            record.failed_parameters = eval_result['failed_parameters']
            record.save()

            # Trigger automated alert if unsafe or caution
            if record.overall_status in ('UNSAFE', 'CAUTION'):
                severity = AlertSeverity.CRITICAL if record.overall_status == 'UNSAFE' else AlertSeverity.WARNING
                reasons = "; ".join([f"{p['parameter_name']}: {p['reason']}" for p in eval_result['failed_parameters']])
                summary = f"Detected {record.overall_status} water quality reading at {record.source.name}. {reasons}"
                
                alert = Alert.objects.create(
                    record=record,
                    source=record.source,
                    status=AlertStatus.NEW,
                    severity=severity,
                    summary=summary
                )

                # Dispatch notifications (email/SMS) to registered recipients.
                # Runs in mock mode by default; configure NOTIFICATION_MOCK_MODE
                # system setting or Django setting for production delivery.
                try:
                    dispatch_result = NotificationService.dispatch_alert(alert)
                    if dispatch_result['recipients_count'] == 0:
                        pass  # No recipients configured yet — alert still saved
                except Exception as notif_exc:
                    # Notification failure must NEVER block record persistence.
                    import logging
                    logging.getLogger(__name__).error(
                        f"Notification dispatch failed for alert {alert.id}: {notif_exc}"
                    )

            log_audit(
                request,
                action="RECORD_CREATE",
                module="WATER_RECORDS",
                record_id=str(record.id),
                details=f"Encoded test for {record.source.name}: Status={record.overall_status} (pH {record.ph_level}, Turbidity {record.turbidity_ntu} NTU, TDS {record.tds_ppm} mg/L)"
            )

            if record.overall_status == 'SAFE':
                messages.success(request, f"Water test saved. Results for '{record.source.name}' evaluated as SAFE.")
            elif record.overall_status == 'CAUTION':
                messages.warning(request, f"Water test saved. Alert created: Parameters approaching limits (CAUTION).")
            else:
                messages.error(request, f"CRITICAL ALERT CREATED: Water test for '{record.source.name}' evaluated as UNSAFE!")

            return redirect('core:record_detail', record_id=record.id)
    else:
        initial = {}
        if source_preselect:
            initial['source'] = source_preselect
        form = WaterQualityRecordForm(initial=initial)

    thresholds = get_thresholds_from_db()
    return render(request, 'records/record_form.html', {
        'form': form,
        'is_edit': False,
        'title': 'Encode Water Quality Test Result',
        'thresholds': thresholds,
    })


@record_entry_required
def record_edit_view(request, record_id):
    """Updates water test record, re-evaluates safety status, and logs audit."""
    record = get_object_or_404(WaterQualityRecord, id=record_id, is_deleted=False)

    if request.method == 'POST':
        form = WaterQualityRecordForm(request.POST, instance=record)
        if form.is_valid():
            updated_record = form.save(commit=False)

            # Re-evaluate safety
            thresholds = get_thresholds_from_db()
            eval_result = evaluate_water_safety(
                ph=updated_record.ph_level,
                turbidity=updated_record.turbidity_ntu,
                tds=updated_record.tds_ppm,
                thresholds=thresholds
            )

            updated_record.overall_status = eval_result['overall_status']
            updated_record.failed_parameters = eval_result['failed_parameters']
            updated_record.save()

            log_audit(
                request,
                action="RECORD_UPDATE",
                module="WATER_RECORDS",
                record_id=str(record.id),
                details=f"Updated test for {record.source.name}: Status now {updated_record.overall_status}"
            )
            messages.success(request, "Water quality test record updated and re-evaluated.")
            return redirect('core:record_detail', record_id=record.id)
    else:
        form = WaterQualityRecordForm(instance=record)

    thresholds = get_thresholds_from_db()
    return render(request, 'records/record_form.html', {
        'form': form,
        'record': record,
        'is_edit': True,
        'title': f'Edit Test Record: {record.source.name}',
        'thresholds': thresholds,
    })


@record_entry_required
def record_delete_view(request, record_id):
    """Soft-deletes a water quality test record."""
    if request.method == 'POST':
        record = get_object_or_404(WaterQualityRecord, id=record_id, is_deleted=False)
        record.is_deleted = True
        record.deleted_at = timezone.now()
        record.deleted_by = request.user
        record.save()

        log_audit(
            request,
            action="RECORD_SOFT_DELETE",
            module="WATER_RECORDS",
            record_id=str(record.id),
            details=f"Soft-deleted test record for {record.source.name} from {record.tested_at.strftime('%Y-%m-%d')}"
        )
        messages.success(request, "Test record has been moved to trash (soft-deleted).")
    return redirect('core:record_list')


@admin_required
def record_restore_view(request, record_id):
    """Restores a soft-deleted test record (Admin privilege)."""
    if request.method == 'POST':
        record = get_object_or_404(WaterQualityRecord, id=record_id, is_deleted=True)
        record.is_deleted = False
        record.deleted_at = None
        record.deleted_by = None
        record.save()

        log_audit(
            request,
            action="RECORD_RESTORE",
            module="WATER_RECORDS",
            record_id=str(record.id),
            details=f"Restored soft-deleted test record for {record.source.name}"
        )
        messages.success(request, f"Test record for '{record.source.name}' has been restored.")
    return redirect('core:record_list')


# ========================================================
# Safety Threshold Management (Admin Only)
# ========================================================

@admin_required
def threshold_list_view(request):
    """Displays configurable water safety standards."""
    thresholds = SafetyThreshold.objects.all()
    return render(request, 'core/threshold_list.html', {'thresholds': thresholds})


@admin_required
def threshold_edit_view(request, threshold_id):
    """Allows Administrator to update standard thresholds and caution margins."""
    threshold = get_object_or_404(SafetyThreshold, id=threshold_id)

    if request.method == 'POST':
        form = SafetyThresholdForm(request.POST, instance=threshold)
        if form.is_valid():
            t = form.save(commit=False)
            t.updated_by = request.user
            t.save()

            log_audit(
                request,
                action="THRESHOLD_UPDATE",
                module="THRESHOLDS",
                record_id=str(t.id),
                details=f"Updated standard for {t.parameter_name}: Min={t.min_safe}, Max={t.max_safe}, CautionMargin={t.caution_margin_percent}%"
            )
            messages.success(request, f"Safety threshold for {t.parameter_name} updated successfully.")
            return redirect('core:threshold_list')
    else:
        form = SafetyThresholdForm(instance=threshold)

    return render(request, 'core/threshold_form.html', {
        'form': form,
        'threshold': threshold,
    })


# ========================================================
# Live Preview API Endpoint (for responsive UX)
# ========================================================

def api_evaluate_preview(request):
    """
    AJAX endpoint called as the technician inputs pH, turbidity, and TDS.
    Returns calculated safety status and reasons for live form feedback.
    """
    ph = request.GET.get('ph')
    turbidity = request.GET.get('turbidity')
    tds = request.GET.get('tds')

    if not ph or not turbidity or not tds:
        return JsonResponse({'status': 'incomplete'})

    try:
        thresholds = get_thresholds_from_db()
        eval_result = evaluate_water_safety(ph=ph, turbidity=turbidity, tds=tds, thresholds=thresholds)
        return JsonResponse(eval_result)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
