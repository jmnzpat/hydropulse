"""
HydroPulse: Alert Lifecycle & Notification Recipient Forms
"""

from django import forms
from core.models import NotificationRecipient, Alert


class NotificationRecipientForm(forms.ModelForm):
    class Meta:
        model = NotificationRecipient
        fields = [
            'name', 'role_title', 'email', 'phone_number',
            'barangay_filter', 'receive_email', 'receive_sms', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Dr. Maria Clara'}),
            'role_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Municipal Health Officer, LGU Sanitary Inspector'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'official@lgu.gov.ph'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+639171234567'}),
            'barangay_filter': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leave empty for all barangays, or specify e.g. San Vicente'
            }),
            'receive_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AlertResolutionForm(forms.Form):
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Describe remediation actions taken (e.g. shock chlorination conducted on Oct 3; casing crack sealed; follow-up water test verified turbidity < 1.0 NTU and pH 7.2).'
        }),
        help_text="Detailed remedial action summary required to transition this alert to RESOLVED status."
    )


class TestNotificationForm(forms.Form):
    channel = forms.ChoiceField(
        choices=[('BOTH', 'Both Email and SMS'), ('EMAIL', 'Email Only'), ('SMS', 'SMS Only')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    custom_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional custom message (defaults to simulated emergency test alert)'
        })
    )
