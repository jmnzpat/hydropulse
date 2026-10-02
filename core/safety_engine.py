"""
HydroPulse: Pure Safety Evaluation Engine
Implements automated evaluation logic based on Philippine National Standards for Drinking Water (PNSDW 2017)
and World Health Organization (WHO) Drinking Water Guidelines.

This module provides pure, side-effect-free functions with zero external dependencies,
making them easily testable and defendable during academic project defense.
"""

from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date


DEFAULT_THRESHOLDS = {
    'ph': {
        'name': 'pH Level',
        'unit': 'pH',
        'min_safe': Decimal('6.50'),
        'max_safe': Decimal('8.50'),
        'caution_margin_percent': Decimal('10.00'),
        'standard_ref': 'PNSDW 2017 Table A (6.5 - 8.5)'
    },
    'turbidity': {
        'name': 'Turbidity',
        'unit': 'NTU',
        'min_safe': None,
        'max_safe': Decimal('5.00'),
        'caution_margin_percent': Decimal('10.00'),
        'standard_ref': 'PNSDW 2017 Table B (max 5 NTU)'
    },
    'tds': {
        'name': 'Total Dissolved Solids (TDS)',
        'unit': 'mg/L',
        'min_safe': None,
        'max_safe': Decimal('600.00'),
        'caution_margin_percent': Decimal('10.00'),
        'standard_ref': 'PNSDW 2017 Table B (max 600 mg/L)'
    }
}


def to_decimal(val: Any) -> Decimal:
    """Helper to safely convert float/str/int to Decimal."""
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid numeric value: {val}")


def validate_test_inputs(
    ph: Any,
    turbidity: Any,
    tds: Any,
    tested_at: Optional[Any] = None
) -> Tuple[bool, List[str]]:
    """
    Validates numeric inputs and physical plausibility ranges:
    - pH: 0.00 to 14.00
    - Turbidity: >= 0.00 NTU
    - TDS: >= 0.00 mg/L
    - tested_at: cannot be in the future
    """
    errors: List[str] = []

    # pH validation
    try:
        ph_dec = to_decimal(ph)
        if ph_dec < Decimal('0.00') or ph_dec > Decimal('14.00'):
            errors.append(f"pH level ({ph}) is outside the physical scale of 0.00 to 14.00.")
    except ValueError:
        errors.append("pH level must be a valid number.")

    # Turbidity validation
    try:
        turb_dec = to_decimal(turbidity)
        if turb_dec < Decimal('0.00'):
            errors.append(f"Turbidity ({turbidity}) cannot be negative.")
        elif turb_dec > Decimal('1000.00'):
            errors.append(f"Turbidity ({turbidity} NTU) exceeds plausible sensor limits (max 1000 NTU).")
    except ValueError:
        errors.append("Turbidity must be a valid number.")

    # TDS validation
    try:
        tds_dec = to_decimal(tds)
        if tds_dec < Decimal('0.00'):
            errors.append(f"Total Dissolved Solids ({tds}) cannot be negative.")
        elif tds_dec > Decimal('10000.00'):
            errors.append(f"TDS ({tds} mg/L) exceeds plausible drinking water testing limits (max 10,000 mg/L).")
    except ValueError:
        errors.append("Total Dissolved Solids must be a valid number.")

    # Test date validation
    if tested_at is not None:
        if isinstance(tested_at, str):
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y-%m-%dT%H:%M'):
                try:
                    tested_at = datetime.strptime(tested_at, fmt)
                    break
                except ValueError:
                    pass
        
        if isinstance(tested_at, datetime):
            if tested_at.tzinfo is not None:
                from datetime import timezone as dt_tz
                now = datetime.now(tested_at.tzinfo)
            else:
                now = datetime.now()
            if tested_at > now:
                errors.append("Test timestamp cannot be in the future.")
        elif isinstance(tested_at, date):
            now = datetime.now().date()
            if tested_at > now:
                errors.append("Test date cannot be in the future.")

    return len(errors) == 0, errors


def evaluate_parameter(
    val: Decimal,
    min_safe: Optional[Decimal],
    max_safe: Optional[Decimal],
    caution_margin_percent: Decimal = Decimal('10.00')
) -> Tuple[str, Optional[str]]:
    """
    Evaluates a single parameter value against min/max limits and caution margin.
    Returns: (status, reason_string)
    status is one of: 'SAFE', 'CAUTION', 'UNSAFE'
    """
    val = to_decimal(val)
    margin_ratio = caution_margin_percent / Decimal('100.00')

    # Case 1: Parameter has both lower and upper limits (e.g. pH 6.5 - 8.5)
    if min_safe is not None and max_safe is not None:
        if val < min_safe:
            return 'UNSAFE', f"Value {val} is below the minimum safe limit of {min_safe}"
        if val > max_safe:
            return 'UNSAFE', f"Value {val} exceeds the maximum safe limit of {max_safe}"
        
        # Caution check: within margin of min_safe or max_safe
        param_range = max_safe - min_safe
        margin_delta = param_range * margin_ratio
        lower_caution_bound = min_safe + margin_delta
        upper_caution_bound = max_safe - margin_delta

        if val <= lower_caution_bound:
            return 'CAUTION', f"Value {val} is within {caution_margin_percent}% of lower safe threshold ({min_safe})"
        if val >= upper_caution_bound:
            return 'CAUTION', f"Value {val} is within {caution_margin_percent}% of upper safe threshold ({max_safe})"
        
        return 'SAFE', None

    # Case 2: Parameter has only upper limit (e.g. Turbidity <= 5.0, TDS <= 600.0)
    elif max_safe is not None:
        if val > max_safe:
            return 'UNSAFE', f"Value {val} exceeds the maximum allowable safe limit of {max_safe}"
        
        caution_delta = max_safe * margin_ratio
        caution_threshold = max_safe - caution_delta
        if val >= caution_threshold:
            return 'CAUTION', f"Value {val} approaches within {caution_margin_percent}% of max threshold ({max_safe})"
        
        return 'SAFE', None

    # Case 3: Parameter has only lower limit
    elif min_safe is not None:
        if val < min_safe:
            return 'UNSAFE', f"Value {val} is below the minimum safe limit of {min_safe}"
        
        caution_delta = min_safe * margin_ratio
        caution_threshold = min_safe + caution_delta
        if val <= caution_threshold:
            return 'CAUTION', f"Value {val} is within {caution_margin_percent}% of lower threshold ({min_safe})"
        
        return 'SAFE', None

    return 'SAFE', None


def evaluate_water_safety(
    ph: Any,
    turbidity: Any,
    tds: Any,
    thresholds: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Pure evaluation function.
    Given pH, turbidity, TDS and threshold dictionary:
    Computes per-parameter status and overall status ('SAFE', 'CAUTION', 'UNSAFE').
    Status rule: Overall status is the worst status among parameters.
    Returns dictionary with full breakdown and failed parameters list.
    """
    cfg = thresholds if thresholds is not None else DEFAULT_THRESHOLDS

    ph_val = to_decimal(ph)
    turb_val = to_decimal(turbidity)
    tds_val = to_decimal(tds)

    evaluations = {}
    failed_parameters = []
    statuses = []

    # Evaluate pH
    ph_cfg = cfg.get('ph', DEFAULT_THRESHOLDS['ph'])
    ph_status, ph_reason = evaluate_parameter(
        ph_val,
        ph_cfg.get('min_safe'),
        ph_cfg.get('max_safe'),
        to_decimal(ph_cfg.get('caution_margin_percent', Decimal('10.00')))
    )
    evaluations['ph'] = {
        'value': float(ph_val),
        'unit': ph_cfg.get('unit', 'pH'),
        'status': ph_status,
        'reason': ph_reason,
        'standard_ref': ph_cfg.get('standard_ref', '')
    }
    statuses.append(ph_status)
    if ph_status != 'SAFE':
        failed_parameters.append({
            'parameter': 'ph',
            'parameter_name': ph_cfg.get('name', 'pH Level'),
            'value': float(ph_val),
            'unit': ph_cfg.get('unit', 'pH'),
            'status': ph_status,
            'reason': ph_reason
        })

    # Evaluate Turbidity
    turb_cfg = cfg.get('turbidity', DEFAULT_THRESHOLDS['turbidity'])
    turb_status, turb_reason = evaluate_parameter(
        turb_val,
        turb_cfg.get('min_safe'),
        turb_cfg.get('max_safe'),
        to_decimal(turb_cfg.get('caution_margin_percent', Decimal('10.00')))
    )
    evaluations['turbidity'] = {
        'value': float(turb_val),
        'unit': turb_cfg.get('unit', 'NTU'),
        'status': turb_status,
        'reason': turb_reason,
        'standard_ref': turb_cfg.get('standard_ref', '')
    }
    statuses.append(turb_status)
    if turb_status != 'SAFE':
        failed_parameters.append({
            'parameter': 'turbidity',
            'parameter_name': turb_cfg.get('name', 'Turbidity'),
            'value': float(turb_val),
            'unit': turb_cfg.get('unit', 'NTU'),
            'status': turb_status,
            'reason': turb_reason
        })

    # Evaluate TDS
    tds_cfg = cfg.get('tds', DEFAULT_THRESHOLDS['tds'])
    tds_status, tds_reason = evaluate_parameter(
        tds_val,
        tds_cfg.get('min_safe'),
        tds_cfg.get('max_safe'),
        to_decimal(tds_cfg.get('caution_margin_percent', Decimal('10.00')))
    )
    evaluations['tds'] = {
        'value': float(tds_val),
        'unit': tds_cfg.get('unit', 'mg/L'),
        'status': tds_status,
        'reason': tds_reason,
        'standard_ref': tds_cfg.get('standard_ref', '')
    }
    statuses.append(tds_status)
    if tds_status != 'SAFE':
        failed_parameters.append({
            'parameter': 'tds',
            'parameter_name': tds_cfg.get('name', 'Total Dissolved Solids'),
            'value': float(tds_val),
            'unit': tds_cfg.get('unit', 'mg/L'),
            'status': tds_status,
            'reason': tds_reason
        })

    # Determine overall status: worst status rule
    # UNSAFE > CAUTION > SAFE
    if 'UNSAFE' in statuses:
        overall_status = 'UNSAFE'
    elif 'CAUTION' in statuses:
        overall_status = 'CAUTION'
    else:
        overall_status = 'SAFE'

    return {
        'overall_status': overall_status,
        'is_safe': overall_status == 'SAFE',
        'is_caution': overall_status == 'CAUTION',
        'is_unsafe': overall_status == 'UNSAFE',
        'parameters': evaluations,
        'failed_parameters': failed_parameters,
    }


def get_thresholds_from_db() -> Dict[str, Dict[str, Any]]:
    """
    Fetches active thresholds from SafetyThreshold database model,
    falling back to DEFAULT_THRESHOLDS if not yet configured or during initial setup.
    """
    try:
        from core.models import SafetyThreshold
        db_thresholds = {}
        for st in SafetyThreshold.objects.all():
            db_thresholds[st.parameter_code] = {
                'name': st.parameter_name,
                'unit': st.unit,
                'min_safe': st.min_safe,
                'max_safe': st.max_safe,
                'caution_margin_percent': st.caution_margin_percent,
                'standard_ref': st.standard_reference
            }
        if db_thresholds:
            return db_thresholds
    except Exception:
        pass
    return DEFAULT_THRESHOLDS
