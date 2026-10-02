"""
HydroPulse: Water Source & Quality Record Forms
Handles input validation, plausible range enforcement, and filtering.
"""

from decimal import Decimal
from django import forms
from django.utils import timezone
from datetime import datetime

from core.models import (
    WaterSource, SourceType, WaterQualityRecord,
    WaterQualityStatus, SafetyThreshold, User, UserRole
)
from core.safety_engine import validate_test_inputs


class WaterSourceForm(forms.ModelForm):
    class Meta:
        model = WaterSource
        fields = [
            'code', 'name', 'source_type', 'barangay',
            'address_details', 'latitude', 'longitude',
            'assigned_engineer', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. WELL-SANVICENTE-01'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Purok 3 Communal Deep Well'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. San Vicente'}),
            'address_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Landmark or description'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001', 'placeholder': 'e.g. 14.599512'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001', 'placeholder': 'e.g. 120.984222'}),
            'assigned_engineer': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit assigned_engineer to users with ENGINEER or ADMIN role
        self.fields['assigned_engineer'].queryset = User.objects.filter(
            role__in=[UserRole.ENGINEER, UserRole.ADMIN], is_active=True
        )
        self.fields['assigned_engineer'].required = False


class WaterQualityRecordForm(forms.ModelForm):
    tested_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text="Date and time when the water sample was collected & tested"
    )

    class Meta:
        model = WaterQualityRecord
        fields = [
            'source', 'tested_at', 'ph_level',
            'turbidity_ntu', 'tds_ppm', 'notes'
        ]
        widgets = {
            'source': forms.Select(attrs={'class': 'form-select'}),
            'ph_level': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g. 7.20 (Standard: 6.5 - 8.5)'
            }),
            'turbidity_ntu': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g. 1.50 NTU (Max standard: 5.0 NTU)'
            }),
            'tds_ppm': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'placeholder': 'e.g. 250.0 mg/L (Max standard: 600.0 mg/L)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Sampling notes, weather conditions, turbidity sensor details, or field observations'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source'].queryset = WaterSource.objects.filter(is_active=True)
        if not self.instance.pk and 'tested_at' not in self.initial:
            self.initial['tested_at'] = timezone.now().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        ph = cleaned_data.get('ph_level')
        turbidity = cleaned_data.get('turbidity_ntu')
        tds = cleaned_data.get('tds_ppm')
        tested_at = cleaned_data.get('tested_at')

        if ph is not None and turbidity is not None and tds is not None:
            is_valid, validation_errors = validate_test_inputs(
                ph=ph,
                turbidity=turbidity,
                tds=tds,
                tested_at=tested_at
            )
            for err in validation_errors:
                self.add_error(None, err)

        return cleaned_data


class SafetyThresholdForm(forms.ModelForm):
    class Meta:
        model = SafetyThreshold
        fields = [
            'min_safe', 'max_safe', 'caution_margin_percent',
            'standard_reference', 'description'
        ]
        widgets = {
            'min_safe': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_safe': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'caution_margin_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'standard_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
