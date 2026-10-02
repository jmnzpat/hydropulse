"""
HydroPulse: Analytics & Surveillance Aggregation Engine
Computes municipal water safety KPIs, parameter trends, barangay compliance rates,
and algorithms to detect recurring water contamination issues.
"""

from decimal import Decimal
from datetime import timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Count, Q, Avg, Max

from core.models import (
    WaterSource, WaterQualityRecord, Alert,
    AlertStatus, AlertSeverity, WaterQualityStatus
)


def get_dashboard_summary_metrics(barangay_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes top-level KPIs for water quality surveillance:
    - Total Monitored Sources (active & inactive)
    - Current safety breakdown (Safe, Caution, Unsafe, Untested)
    - Active unacknowledged & acknowledged alerts
    - Municipal overall compliance rate %
    """
    sources_qs = WaterSource.objects.all()
    records_qs = WaterQualityRecord.objects.filter(is_deleted=False)
    alerts_qs = Alert.objects.all()

    if barangay_filter:
        sources_qs = sources_qs.filter(barangay__iexact=barangay_filter)
        records_qs = records_qs.filter(source__barangay__iexact=barangay_filter)
        alerts_qs = alerts_qs.filter(source__barangay__iexact=barangay_filter)

    total_sources = sources_qs.count()
    active_sources = sources_qs.filter(is_active=True).count()
    inactive_sources = total_sources - active_sources

    # Calculate status per source based on their latest non-deleted test record
    safe_sources_count = 0
    caution_sources_count = 0
    unsafe_sources_count = 0
    untested_sources_count = 0

    sources_with_latest = sources_qs.prefetch_related('records')
    for src in sources_with_latest:
        st = src.current_status
        if st == 'SAFE':
            safe_sources_count += 1
        elif st == 'CAUTION':
            caution_sources_count += 1
        elif st == 'UNSAFE':
            unsafe_sources_count += 1
        else:
            untested_sources_count += 1

    tested_sources_total = safe_sources_count + caution_sources_count + unsafe_sources_count
    compliance_rate = (
        round((safe_sources_count / tested_sources_total) * 100, 1)
        if tested_sources_total > 0 else 100.0
    )

    # Test records counts
    total_tests = records_qs.count()
    safe_tests = records_qs.filter(overall_status=WaterQualityStatus.SAFE).count()
    caution_tests = records_qs.filter(overall_status=WaterQualityStatus.CAUTION).count()
    unsafe_tests = records_qs.filter(overall_status=WaterQualityStatus.UNSAFE).count()

    # Alerts breakdown
    new_alerts_count = alerts_qs.filter(status=AlertStatus.NEW).count()
    acknowledged_alerts_count = alerts_qs.filter(status=AlertStatus.ACKNOWLEDGED).count()
    resolved_alerts_count = alerts_qs.filter(status=AlertStatus.RESOLVED).count()

    return {
        'total_sources': total_sources,
        'active_sources': active_sources,
        'inactive_sources': inactive_sources,
        'safe_sources_count': safe_sources_count,
        'caution_sources_count': caution_sources_count,
        'unsafe_sources_count': unsafe_sources_count,
        'untested_sources_count': untested_sources_count,
        'tested_sources_total': tested_sources_total,
        'compliance_rate': compliance_rate,
        'total_tests': total_tests,
        'safe_tests': safe_tests,
        'caution_tests': caution_tests,
        'unsafe_tests': unsafe_tests,
        'new_alerts_count': new_alerts_count,
        'acknowledged_alerts_count': acknowledged_alerts_count,
        'resolved_alerts_count': resolved_alerts_count,
        'active_alerts_total': new_alerts_count + acknowledged_alerts_count,
    }


def get_safety_distribution_data(barangay_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns chart-ready data structure for safety distribution doughnut chart.
    """
    metrics = get_dashboard_summary_metrics(barangay_filter)
    return {
        'labels': ['Safe (Potable)', 'Caution (Approaching Limits)', 'Unsafe (Contaminated)', 'Untested'],
        'counts': [
            metrics['safe_sources_count'],
            metrics['caution_sources_count'],
            metrics['unsafe_sources_count'],
            metrics['untested_sources_count']
        ],
        'colors': ['#059669', '#d97706', '#dc2626', '#94a3b8']
    }


def get_parameter_timeline_data(
    source_id: Optional[int] = None,
    barangay_filter: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Returns chronological timeline data for Chart.js line charts.
    Includes parameter values (pH, Turbidity, TDS) and regulatory guideline bounds.
    """
    records_qs = WaterQualityRecord.objects.filter(is_deleted=False).select_related('source')

    if source_id:
        records_qs = records_qs.filter(source_id=source_id)
    elif barangay_filter:
        records_qs = records_qs.filter(source__barangay__iexact=barangay_filter)

    # Order chronologically for line charts
    recent_records = list(records_qs.order_by('-tested_at')[:limit])
    recent_records.reverse()

    labels = [r.tested_at.strftime('%b %d %H:%M') for r in recent_records]
    ph_data = [float(r.ph_level) for r in recent_records]
    turbidity_data = [float(r.turbidity_ntu) for r in recent_records]
    tds_data = [float(r.tds_ppm) for r in recent_records]

    return {
        'labels': labels,
        'ph_data': ph_data,
        'turbidity_data': turbidity_data,
        'tds_data': tds_data,
        # Reference lines for PNSDW 2017 thresholds
        'thresholds': {
            'ph_min': 6.5,
            'ph_max': 8.5,
            'turbidity_max': 5.0,
            'tds_max': 600.0,
        }
    }


def get_barangay_compliance_data() -> Dict[str, Any]:
    """
    Aggregates safety compliance per barangay for comparative bar chart.
    """
    barangays = list(WaterSource.objects.values_list('barangay', flat=True).distinct())
    
    chart_labels = []
    safe_counts = []
    caution_counts = []
    unsafe_counts = []

    for b in barangays:
        if not b:
            continue
        chart_labels.append(b)
        records = WaterQualityRecord.objects.filter(source__barangay__iexact=b, is_deleted=False)
        safe_counts.append(records.filter(overall_status=WaterQualityStatus.SAFE).count())
        caution_counts.append(records.filter(overall_status=WaterQualityStatus.CAUTION).count())
        unsafe_counts.append(records.filter(overall_status=WaterQualityStatus.UNSAFE).count())

    return {
        'labels': chart_labels,
        'safe_counts': safe_counts,
        'caution_counts': caution_counts,
        'unsafe_counts': unsafe_counts,
    }


def get_recurring_issues(fail_threshold: int = 2, test_window: int = 5) -> List[Dict[str, Any]]:
    """
    Algorithmic recurring-issue detector:
    Identifies water sources that have failed or triggered caution in $\ge$ fail_threshold
    of their most recent test_window readings.
    Provides academic defensibility for preventive intervention.
    """
    recurring_issues = []
    active_sources = WaterSource.objects.filter(is_active=True).prefetch_related('records')

    for src in active_sources:
        recent_tests = list(src.records.filter(is_deleted=False).order_by('-tested_at')[:test_window])
        if not recent_tests:
            continue

        non_safe_tests = [t for t in recent_tests if t.overall_status in ('UNSAFE', 'CAUTION')]
        unsafe_tests = [t for t in recent_tests if t.overall_status == 'UNSAFE']

        if len(non_safe_tests) >= fail_threshold:
            # Analyze primary violated parameter
            ph_violations = 0
            turb_violations = 0
            tds_violations = 0

            for t in non_safe_tests:
                for f in t.failed_parameters:
                    param = f.get('parameter')
                    if param == 'ph':
                        ph_violations += 1
                    elif param == 'turbidity':
                        turb_violations += 1
                    elif param == 'tds':
                        tds_violations += 1

            reasons = []
            if turb_violations > 0:
                reasons.append(f"Turbidity instability ({turb_violations}x)")
            if ph_violations > 0:
                reasons.append(f"pH abnormalities ({ph_violations}x)")
            if tds_violations > 0:
                reasons.append(f"High dissolved solids ({tds_violations}x)")

            # Recommended sanitary intervention
            intervention = "Sanitary inspection and localized well chlorination recommended."
            if turb_violations >= ph_violations and turb_violations >= tds_violations:
                intervention = "Inspect well casing integrity for surface runoff infiltration; flush distribution lines."
            elif tds_violations > turb_violations:
                intervention = "Check for mineral leaching or aquifer contamination; conduct comprehensive chemical assay."

            severity = 'CRITICAL' if len(unsafe_tests) >= 2 else 'WARNING'

            recurring_issues.append({
                'source': src,
                'severity': severity,
                'fail_count': len(non_safe_tests),
                'window': len(recent_tests),
                'primary_issues': ", ".join(reasons) if reasons else "Multiple parameter fluctuations",
                'latest_test': recent_tests[0],
                'recommended_action': intervention
            })

    # Sort critical first, then highest fail count
    recurring_issues.sort(key=lambda x: (x['severity'] == 'CRITICAL', x['fail_count']), reverse=True)
    return recurring_issues


def get_sources_due_for_testing(days_overdue: int = 14) -> List[Dict[str, Any]]:
    """
    Identifies active water sources that have not been tested within the recommended
    surveillance interval (e.g. 14 days), helping sanitation engineers schedule fieldwork.
    """
    cutoff = timezone.now() - timedelta(days=days_overdue)
    due_sources = []

    for src in WaterSource.objects.filter(is_active=True):
        latest = src.latest_record
        if not latest:
            due_sources.append({
                'source': src,
                'days_since_test': None,
                'status': 'NEVER_TESTED'
            })
        elif latest.tested_at < cutoff:
            days_ago = (timezone.now() - latest.tested_at).days
            due_sources.append({
                'source': src,
                'days_since_test': days_ago,
                'status': 'OVERDUE'
            })

    return due_sources
