"""
HydroPulse: Dashboard & Analytics Views
Powers interactive surveillance visualizations, KPI status cards,
per-source matrices, and recurring contamination alerts.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Prefetch

from core.models import (
    WaterSource, WaterQualityRecord, Alert,
    AlertStatus, UserRole
)
from core import analytics


@login_required
def dashboard_view(request):
    """
    Main interactive analytics dashboard for Health Officers, Sanitation Engineers, and Admins.
    Displays real-time KPIs, parameter trends, safe vs unsafe breakdowns, and recurring issues.
    """
    barangay_filter = request.GET.get('barangay', '').strip()
    
    # 1. Summary Metrics & KPIs
    metrics = analytics.get_dashboard_summary_metrics(barangay_filter)

    # 2. Chart Datasets
    safety_distribution = analytics.get_safety_distribution_data(barangay_filter)
    parameter_timeline = analytics.get_parameter_timeline_data(barangay_filter=barangay_filter, limit=15)
    barangay_compliance = analytics.get_barangay_compliance_data()

    # 3. Surveillance Highlights & Field Alerts
    recurring_issues = analytics.get_recurring_issues(fail_threshold=2, test_window=5)
    sources_due = analytics.get_sources_due_for_testing(days_overdue=14)

    # 4. Recent Active Alerts
    recent_alerts = Alert.objects.filter(
        status__in=[AlertStatus.NEW, AlertStatus.ACKNOWLEDGED]
    ).select_related('source', 'record').order_by('-created_at')[:6]

    # 5. Monitored Sources Status Matrix
    sources_qs = WaterSource.objects.filter(is_active=True).select_related('assigned_engineer')
    if barangay_filter:
        sources_qs = sources_qs.filter(barangay__iexact=barangay_filter)
    
    sources_matrix = list(sources_qs.order_by('barangay', 'name'))

    # Distinct barangays for filter dropdown
    distinct_barangays = WaterSource.objects.values_list('barangay', flat=True).distinct()

    return render(request, 'dashboard/dashboard.html', {
        'metrics': metrics,
        'safety_distribution': safety_distribution,
        'parameter_timeline': parameter_timeline,
        'barangay_compliance': barangay_compliance,
        'recurring_issues': recurring_issues,
        'sources_due': sources_due,
        'recent_alerts': recent_alerts,
        'sources_matrix': sources_matrix,
        'distinct_barangays': distinct_barangays,
        'selected_barangay': barangay_filter,
    })


@login_required
def api_dashboard_charts(request):
    """
    JSON API endpoint for asynchronous Chart.js re-renders based on selected source or barangay.
    """
    source_id = request.GET.get('source_id')
    barangay = request.GET.get('barangay')

    timeline = analytics.get_parameter_timeline_data(
        source_id=int(source_id) if source_id else None,
        barangay_filter=barangay,
        limit=20
    )
    distribution = analytics.get_safety_distribution_data(barangay)

    return JsonResponse({
        'timeline': timeline,
        'distribution': distribution,
    })
