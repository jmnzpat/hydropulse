"""
Unit tests for Pure Safety Evaluation Engine.
Tests all boundary conditions, caution margins, unsafe limits, and physical validation.
Defendable in academic review: covers PNSDW 2017 & WHO Drinking Water Guidelines.
"""

from decimal import Decimal
from datetime import datetime, timedelta
import pytest

from core.safety_engine import (
    evaluate_water_safety,
    evaluate_parameter,
    validate_test_inputs,
    DEFAULT_THRESHOLDS
)


class TestSafetyEnginePureFunction:

    def test_all_parameters_safe(self):
        """Values squarely in the middle of safe ranges should yield SAFE."""
        result = evaluate_water_safety(
            ph=7.20,
            turbidity=1.50,
            tds=250.00
        )
        assert result['overall_status'] == 'SAFE'
        assert result['is_safe'] is True
        assert result['is_caution'] is False
        assert result['is_unsafe'] is False
        assert len(result['failed_parameters']) == 0

    def test_ph_lower_boundary_unsafe(self):
        """pH < 6.5 must be marked UNSAFE."""
        result = evaluate_water_safety(ph=6.49, turbidity=2.0, tds=300.0)
        assert result['overall_status'] == 'UNSAFE'
        assert result['parameters']['ph']['status'] == 'UNSAFE'
        assert any(f['parameter'] == 'ph' for f in result['failed_parameters'])

    def test_ph_upper_boundary_unsafe(self):
        """pH > 8.5 must be marked UNSAFE."""
        result = evaluate_water_safety(ph=8.51, turbidity=2.0, tds=300.0)
        assert result['overall_status'] == 'UNSAFE'
        assert result['parameters']['ph']['status'] == 'UNSAFE'

    def test_ph_lower_caution_margin(self):
        """
        pH Range is 6.5 to 8.5 (span = 2.0). 10% margin is 0.20.
        pH between 6.50 and 6.70 should trigger CAUTION.
        """
        result = evaluate_water_safety(ph=6.60, turbidity=2.0, tds=300.0)
        assert result['overall_status'] == 'CAUTION'
        assert result['parameters']['ph']['status'] == 'CAUTION'
        assert result['is_caution'] is True

    def test_ph_upper_caution_margin(self):
        """
        pH between 8.30 and 8.50 should trigger CAUTION.
        """
        result = evaluate_water_safety(ph=8.40, turbidity=2.0, tds=300.0)
        assert result['overall_status'] == 'CAUTION'
        assert result['parameters']['ph']['status'] == 'CAUTION'

    def test_turbidity_safe(self):
        """Turbidity <= 4.5 NTU (more than 10% below 5.0) should be SAFE."""
        result = evaluate_water_safety(ph=7.0, turbidity=3.5, tds=300.0)
        assert result['parameters']['turbidity']['status'] == 'SAFE'

    def test_turbidity_caution_margin(self):
        """
        Turbidity max is 5.0 NTU. 10% margin is 0.5 NTU.
        Values between 4.50 and 5.00 NTU should trigger CAUTION.
        """
        result = evaluate_water_safety(ph=7.0, turbidity=4.80, tds=300.0)
        assert result['overall_status'] == 'CAUTION'
        assert result['parameters']['turbidity']['status'] == 'CAUTION'

    def test_turbidity_unsafe_boundary(self):
        """Turbidity > 5.0 NTU must trigger UNSAFE."""
        result = evaluate_water_safety(ph=7.0, turbidity=5.01, tds=300.0)
        assert result['overall_status'] == 'UNSAFE'
        assert result['parameters']['turbidity']['status'] == 'UNSAFE'

    def test_tds_caution_margin(self):
        """
        TDS max is 600.0 mg/L. 10% margin is 60.0 mg/L.
        Values between 540.0 and 600.0 mg/L should trigger CAUTION.
        """
        result = evaluate_water_safety(ph=7.0, turbidity=2.0, tds=570.0)
        assert result['overall_status'] == 'CAUTION'
        assert result['parameters']['tds']['status'] == 'CAUTION'

    def test_tds_unsafe_boundary(self):
        """TDS > 600.0 mg/L must trigger UNSAFE."""
        result = evaluate_water_safety(ph=7.0, turbidity=2.0, tds=605.0)
        assert result['overall_status'] == 'UNSAFE'
        assert result['parameters']['tds']['status'] == 'UNSAFE'

    def test_worst_status_rule(self):
        """
        If one parameter is CAUTION and another is UNSAFE,
        the overall status MUST be UNSAFE (worst-status principle).
        """
        result = evaluate_water_safety(
            ph=6.60,      # Caution (approaching 6.5)
            turbidity=7.50, # Unsafe (> 5.0 NTU)
            tds=200.0     # Safe
        )
        assert result['overall_status'] == 'UNSAFE'
        assert len(result['failed_parameters']) == 2
        statuses = [f['status'] for f in result['failed_parameters']]
        assert 'CAUTION' in statuses
        assert 'UNSAFE' in statuses

    def test_custom_threshold_override(self):
        """System Administrator custom thresholds should override defaults seamlessly."""
        custom_thresholds = {
            'ph': {
                'name': 'Strict pH',
                'unit': 'pH',
                'min_safe': Decimal('7.00'),
                'max_safe': Decimal('8.00'),
                'caution_margin_percent': Decimal('5.00'),
                'standard_ref': 'Custom Strict Standard'
            },
            'turbidity': DEFAULT_THRESHOLDS['turbidity'],
            'tds': DEFAULT_THRESHOLDS['tds'],
        }
        # Under default standard, pH 6.8 is safe. Under custom (min 7.0), it is unsafe.
        result = evaluate_water_safety(ph=6.80, turbidity=2.0, tds=300.0, thresholds=custom_thresholds)
        assert result['overall_status'] == 'UNSAFE'
        assert result['parameters']['ph']['status'] == 'UNSAFE'


class TestInputValidation:

    def test_valid_inputs(self):
        is_valid, errors = validate_test_inputs(
            ph=7.2,
            turbidity=3.1,
            tds=250.0,
            tested_at=datetime.now() - timedelta(hours=1)
        )
        assert is_valid is True
        assert len(errors) == 0

    def test_ph_out_of_physical_range(self):
        is_valid, errors = validate_test_inputs(ph=15.0, turbidity=2.0, tds=200.0)
        assert is_valid is False
        assert any("physical scale" in e for e in errors)

    def test_negative_turbidity(self):
        is_valid, errors = validate_test_inputs(ph=7.0, turbidity=-1.0, tds=200.0)
        assert is_valid is False
        assert any("cannot be negative" in e for e in errors)

    def test_negative_tds(self):
        is_valid, errors = validate_test_inputs(ph=7.0, turbidity=2.0, tds=-50.0)
        assert is_valid is False
        assert any("cannot be negative" in e for e in errors)

    def test_future_test_date_rejected(self):
        future_date = datetime.now() + timedelta(days=2)
        is_valid, errors = validate_test_inputs(
            ph=7.0,
            turbidity=2.0,
            tds=200.0,
            tested_at=future_date
        )
        assert is_valid is False
        assert any("future" in e.lower() for e in errors)
