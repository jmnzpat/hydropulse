"""
Unit and Integration Tests for Phase 3: Analytics, Trends, and Dashboard
Tests KPI calculations, recurring issue algorithms, and dashboard views.
"""

from decimal import Decimal
from datetime import timedelta
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.models import (
    User, UserRole, WaterSource, SourceType,
    WaterQualityRecord, WaterQualityStatus, Alert
)
from core import analytics


@pytest.mark.django_db
class TestAnalyticsEngine:

    def setup_method(self):
        self.client = Client()
        self.health_officer = User.objects.create_user(
            username='health_tester', password='password123', role=UserRole.HEALTH_OFFICER
        )

        # Create two sources in different barangays
        self.source1 = WaterSource.objects.create(
            code='SRC-A1', name='Source Alpha', source_type=SourceType.DEEP_WELL,
            barangay='Barangay Alpha', is_active=True
        )
        self.source2 = WaterSource.objects.create(
            code='SRC-B2', name='Source Beta', source_type=SourceType.SPRING,
            barangay='Barangay Beta', is_active=True
        )

        now = timezone.now()

        # Source 1: 1 safe test
        WaterQualityRecord.objects.create(
            source=self.source1, tested_at=now - timedelta(days=2),
            ph_level=Decimal('7.2'), turbidity_ntu=Decimal('1.0'), tds_ppm=Decimal('200.0'),
            overall_status=WaterQualityStatus.SAFE
        )

        # Source 2: 2 unsafe tests in a row (triggering recurring issues)
        WaterQualityRecord.objects.create(
            source=self.source2, tested_at=now - timedelta(days=3),
            ph_level=Decimal('8.9'), turbidity_ntu=Decimal('8.2'), tds_ppm=Decimal('450.0'),
            overall_status=WaterQualityStatus.UNSAFE,
            failed_parameters=[
                {'parameter': 'turbidity', 'parameter_name': 'Turbidity', 'reason': 'Exceeds 5 NTU'},
                {'parameter': 'ph', 'parameter_name': 'pH Level', 'reason': 'Exceeds 8.5'}
            ]
        )
        WaterQualityRecord.objects.create(
            source=self.source2, tested_at=now - timedelta(days=1),
            ph_level=Decimal('8.7'), turbidity_ntu=Decimal('6.5'), tds_ppm=Decimal('420.0'),
            overall_status=WaterQualityStatus.UNSAFE,
            failed_parameters=[
                {'parameter': 'turbidity', 'parameter_name': 'Turbidity', 'reason': 'Exceeds 5 NTU'}
            ]
        )

    def test_summary_metrics_all(self):
        metrics = analytics.get_dashboard_summary_metrics()
        assert metrics['total_sources'] == 2
        assert metrics['safe_sources_count'] == 1
        assert metrics['unsafe_sources_count'] == 1
        assert metrics['compliance_rate'] == 50.0  # 1 out of 2 tested sources is safe
        assert metrics['total_tests'] == 3
        assert metrics['safe_tests'] == 1
        assert metrics['unsafe_tests'] == 2

    def test_summary_metrics_filtered_by_barangay(self):
        metrics_alpha = analytics.get_dashboard_summary_metrics(barangay_filter='Barangay Alpha')
        assert metrics_alpha['total_sources'] == 1
        assert metrics_alpha['safe_sources_count'] == 1
        assert metrics_alpha['unsafe_sources_count'] == 0
        assert metrics_alpha['compliance_rate'] == 100.0

        metrics_beta = analytics.get_dashboard_summary_metrics(barangay_filter='Barangay Beta')
        assert metrics_beta['total_sources'] == 1
        assert metrics_beta['safe_sources_count'] == 0
        assert metrics_beta['unsafe_sources_count'] == 1
        assert metrics_beta['compliance_rate'] == 0.0

    def test_recurring_issues_algorithm(self):
        """Source 2 has 2 unsafe tests in a row, should be flagged as recurring issue."""
        recurring = analytics.get_recurring_issues(fail_threshold=2, test_window=5)
        assert len(recurring) == 1
        issue = recurring[0]
        assert issue['source'] == self.source2
        assert issue['fail_count'] == 2
        assert issue['severity'] == 'CRITICAL'
        assert 'Turbidity' in issue['primary_issues']

    def test_parameter_timeline_data(self):
        timeline = analytics.get_parameter_timeline_data(source_id=self.source2.id)
        assert len(timeline['labels']) == 2
        assert len(timeline['ph_data']) == 2
        assert len(timeline['turbidity_data']) == 2
        assert timeline['turbidity_data'] == [8.2, 6.5]  # chronological order (older first)

    def test_dashboard_view_authenticated(self):
        self.client.login(username='health_tester', password='password123')
        response = self.client.get(reverse('core:dashboard'))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Water Surveillance Dashboard' in content
        assert 'Source Alpha' in content
        assert 'Source Beta' in content
        assert 'Recurring Water Quality Issue Highlights' in content

    def test_dashboard_charts_api(self):
        self.client.login(username='health_tester', password='password123')
        response = self.client.get(reverse('core:api_dashboard_charts'))
        assert response.status_code == 200
        data = response.json()
        assert 'timeline' in data
        assert 'distribution' in data
        assert 'labels' in data['timeline']
