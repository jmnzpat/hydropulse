"""
HydroPulse: Authentication & User Management Forms
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from core.models import UserRole, SystemSetting

User = get_user_model()


class HydroPulseLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your username',
            'autocomplete': 'username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })
    )


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Initial account password'}),
        help_text="Must be at least 8 characters long."
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm account password'})
    )

    class Meta:
        model = User
        fields = [
            'username', 'role', 'first_name', 'last_name',
            'email', 'phone_number', 'barangay', 'employee_id', 'is_active'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+63 9xx xxx xxxx'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. San Pedro'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SE-2026-004'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'role', 'first_name', 'last_name', 'email',
            'phone_number', 'barangay', 'employee_id', 'is_active'
        ]
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'barangay']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'barangay': forms.TextInput(attrs={'class': 'form-control'}),
        }


class SystemSettingsForm(forms.Form):
    allow_health_officer_data_entry = forms.BooleanField(
        required=False,
        label="Allow Health Officers to Input & Edit Test Data",
        help_text="Addresses the proposal specification nuance: Check this to allow Health Officers to encode tests in addition to Sanitation Engineers.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    caution_margin_percent = forms.DecimalField(
        min_value=1.0,
        max_value=30.0,
        decimal_places=2,
        label="Default Caution Margin (%)",
        help_text="Percentage margin from standard limits that flags parameters as CAUTION (Default: 10.0%).",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'})
    )
    notification_mock_mode = forms.BooleanField(
        required=False,
        label="Enable Notification Simulation Mode (Mock)",
        help_text="When checked, alerts are simulated and logged to the database without requiring live external SMS/SMTP credits.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
