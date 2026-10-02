"""
Integration and Unit Tests for Water Sources, Test Records, and Automated Evaluation
Defends the complete Phase 2 workflow in academic review.
"""

from decimal import Decimal
from datetime import datetime, timedelta
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.models import (
    User, UserRole, WaterSource, SourceType,
    WaterQualityRecord, Alert, SafetyThreshold, AuditLog
)
from core.safety_engine import evaluate_water_safety


@pytest.mark.django_db
class TestWaterSourcesAndRecords:

    def setup_method(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_tester', password='password123', role=UserRole.ADMIN
        )
        self.engineer = User.objects.create_user(
            username='engr_tester', password='password123', role=UserRole.ENGINEER
        )
        self.resident = User.objects.create_user(
            username='res_tester', password='password123', role=UserRole.RESIDENT
        )

        # Setup standard thresholds
        SafetyThreshold.objects.create(
            parameter_code='ph', parameter_name='pH Level', unit='pH',
            min_safe=Decimal('6.50'), max_safe=Decimal('8.50'), caution_margin_percent=Decimal('10.00')
        )
        SafetyThreshold.objects.create(
            parameter_code='turbidity', parameter_name='Turbidity', unit='NTU',
            min_safe=None, max_safe=Decimal('5.00'), caution_margin_percent=Decimal('10.00')
        )
        SafetyThreshold.objects.create(
            parameter_code='tds', parameter_name='TDS', unit='mg/L',
            min_safe=None, max_safe=Decimal('600.00'), caution_margin_percent=Decimal('10.00')
        )

        self.source = WaterSource.objects.create(
            code='SRC-TEST-01',
            name='Test Deep Well',
            source_type=SourceType.DEEP_WELL,
            barangay='San Vicente',
            assigned_engineer=self.engineer
        )

    def test_create_safe_water_record(self):
        """Encoding safe readings yields SAFE status and no alert."""
        self.client.login(username='engr_tester', password='password123')
        response = self.client.post(reverse('core:record_create'), {
            'source': self.source.id,
            'tested_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'ph_level': '7.20',
            'turbidity_ntu': '1.50',
            'tds_ppm': '250.0',
            'notes': 'Normal clear test'
        })
        assert response.status_code == 302
        record = WaterQualityRecord.objects.get(source=self.source, ph_level=Decimal('7.20'))
        assert record.overall_status == 'SAFE'
        assert len(record.failed_parameters) == 0
        assert Alert.objects.filter(record=record).count() == 0
        assert AuditLog.objects.filter(action='RECORD_CREATE', record_id=str(record.id)).exists()

    def test_create_unsafe_water_record_triggers_alert(self):
        """Encoding unsafe readings yields UNSAFE status and creates an automated Alert."""
        self.client.login(username='engr_tester', password='password123')
        response = self.client.post(reverse('core:record_create'), {
            'source': self.source.id,
            'tested_at': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'ph_level': '9.10',        # Unsafe (> 8.5)
            'turbidity_ntu': '7.50',   # Unsafe (> 5.0)
            'tds_ppm': '300.0',
            'notes': 'Contamination observed'
        })
        assert response.status_code == 302
        record = WaterQualityRecord.objects.get(source=self.source, ph_level=Decimal('9.10'))
        assert record.overall_status == 'UNSAFE'
        assert len(record.failed_parameters) == 2

        # Verify automated alert creation
        alert = Alert.objects.filter(record=record).first()
        assert alert is not None
        assert alert.severity == 'CRITICAL'
        assert alert.status == 'NEW'
        assert '9.1' in alert.summary or 'pH' in alert.summary

    def test_soft_delete_and_restore(self):
        """Test record soft deletion preserves data and allows admin restoration."""
        record = WaterQualityRecord.objects.create(
            source=self.source,
            tested_by=self.engineer,
            tested_at=timezone.now(),
            ph_level=Decimal('7.0'),
            turbidity_ntu=Decimal('2.0'),
            tds_ppm=Decimal('300.0'),
            overall_status='SAFE'
        )

        # Engineer soft deletes
        self.client.login(username='engr_tester', password='password123')
        del_resp = self.client.post(reverse('core:record_delete', kwargs={'record_id': record.id}))
        assert del_resp.status_code == 302
        record.refresh_from_db()
        assert record.is_deleted is True
        assert record.deleted_by == self.engineer

        # Excluded from regular list query
        assert record not in WaterQualityRecord.objects.filter(is_deleted=False)

        # Admin restores
        self.client.login(username='admin_tester', password='password123')
        res_resp = self.client.post(reverse('core:record_restore', kwargs={'record_id': record.id}))
        assert res_resp.status_code == 302
        record.refresh_from_db()
        assert record.is_deleted is False
        assert record.deleted_by is None

    def test_future_date_rejected_by_form(self):
        """Form validation prevents test dates set in the future."""
        self.client.login(username='engr_tester', password='password123')
        future_time = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(reverse('core:record_create'), {
            'source': self.source.id,
            'tested_at': future_time,
            'ph_level': '7.0',
            'turbidity_ntu': '2.0',
            'tds_ppm': '300.0'
        })
        assert response.status_code == 200
        assert "future" in response.content.decode().lower()

    def test_live_preview_api(self):
        """API returns real-time calculated evaluation for form inputs."""
        response = self.client.get(reverse('core:api_evaluate_preview'), {
            'ph': '6.60',          # Caution
            'turbidity': '4.80',   # Caution
            'tds': '200.0'         # Safe
        })
        assert response.status_code == 200
        data = response.json()
        assert data['overall_status'] == 'CAUTION'
        assert data['is_caution'] is True
        assert len(data['failed_parameters']) == 2
