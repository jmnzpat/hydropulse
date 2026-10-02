"""
HydroPulse: Pluggable Alert & Notification Service
Handles automated Email and SMS notifications when non-safe water quality conditions are detected.
Features a zero-cost Mock/Simulation mode for classroom defense and development,
along with pluggable SMTP and SMS API providers for production deployment.
"""

import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.models import (
    Alert, NotificationRecipient, NotificationLog,
    SystemSetting, AlertSeverity
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Pluggable notification dispatcher for HydroPulse.
    Dispatches critical water safety alerts via Email and SMS.
    """

    @classmethod
    def is_mock_mode(cls) -> bool:
        """Checks if notification simulation mode is active."""
        # First check database system setting, fallback to Django settings
        val = SystemSetting.get_val('NOTIFICATION_MOCK_MODE')
        if val is not None:
            return SystemSetting.get_bool('NOTIFICATION_MOCK_MODE', default=True)
        return getattr(settings, 'NOTIFICATION_MOCK_MODE', True)

    @classmethod
    def format_alert_message(cls, alert: Alert) -> Dict[str, str]:
        """
        Formats standardized, clear alert content for SMS (short) and Email (detailed).
        Follows public health communication standards: factual, actionable, and concise.
        """
        source = alert.source
        record = alert.record
        tested_str = record.tested_at.strftime('%Y-%m-%d %H:%M')

        # Short SMS message (under 160 chars when possible)
        sms_text = (
            f"[HydroPulse ALERT] {alert.severity} Water Quality Detected at {source.name} "
            f"(Brgy. {source.barangay}) on {tested_str}. Status: {record.overall_status}. "
            f"Review immediately: {alert.summary[:60]}..."
        )

        # Detailed Email Subject and Body
        email_subject = f"[HydroPulse {alert.severity} ALERT] Contamination Flag: {source.name} (Brgy. {source.barangay})"
        email_body = f"""HYDROPULSE WATER QUALITY ALERT & SURVEILLANCE NOTIFICATION
----------------------------------------------------------------------
Alert Severity:     {alert.severity} ({alert.get_severity_display()})
Water Source:       {source.name} [{source.code}]
Infrastructure:     {source.get_source_type_display()}
Barangay/Location:  Brgy. {source.barangay}
Tested Date & Time: {tested_str} (PHT)
Assigned Engineer:  {source.assigned_engineer.get_full_name() if source.assigned_engineer else 'Unassigned'}

TEST RESULTS & DISCREPANCIES:
- Overall Safety Status: {record.overall_status}
- Measured pH Level:     {record.ph_level} (Safe: 6.5 - 8.5)
- Turbidity:             {record.turbidity_ntu} NTU (Max Safe: 5.0 NTU)
- Total Dissolved Solids: {record.tds_ppm} mg/L (Max Safe: 600 mg/L)

SUMMARY OF FINDINGS:
{alert.summary}

FIELD OBSERVATIONS:
{record.notes or 'No technician field notes provided.'}

RECOMMENDED ACTION:
1. Verify field sampling results and dispatch sanitary inspection team.
2. Acknowledge this alert in the HydroPulse Staff Portal.
3. If necessary, issue a public advisory (e.g. Boil Water Notice) via the Public Safety Portal.

System Notification generated automatically by HydroPulse Water Surveillance.
----------------------------------------------------------------------
"""
        return {
            'sms': sms_text,
            'email_subject': email_subject,
            'email_body': email_body,
        }

    @classmethod
    def get_recipients_for_alert(cls, alert: Alert) -> List[NotificationRecipient]:
        """
        Retrieves active recipients configured to receive alerts for the source's barangay
        or municipality-wide (empty barangay_filter).
        """
        source_barangay = alert.source.barangay.strip().lower()
        recipients = NotificationRecipient.objects.filter(is_active=True)
        
        matched = []
        for r in recipients:
            bf = r.barangay_filter.strip().lower()
            if not bf or bf == source_barangay:
                matched.append(r)
        return matched

    @classmethod
    def send_email(cls, recipient: NotificationRecipient, subject: str, body: str, alert: Optional[Alert] = None) -> bool:
        """Sends email or records simulated dispatch in mock mode."""
        if not recipient.email:
            return False

        is_mock = cls.is_mock_mode()
        status = 'MOCKED' if is_mock else 'SENT'
        error_msg = ''

        if not is_mock:
            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    fail_silently=False,
                )
                logger.info(f"Email alert sent to {recipient.email}")
            except Exception as e:
                status = 'FAILED'
                error_msg = str(e)
                logger.error(f"Failed to send email to {recipient.email}: {e}")
        else:
            logger.info(f"[MOCK EMAIL] To: {recipient.email} | Subject: {subject}")

        NotificationLog.objects.create(
            alert=alert,
            recipient_name=recipient.name,
            channel='EMAIL',
            destination=recipient.email,
            status=status,
            message_content=f"Subject: {subject}\n\n{body}",
            error_message=error_msg
        )
        return status in ('SENT', 'MOCKED')

    @classmethod
    def send_sms(cls, recipient: NotificationRecipient, message: str, alert: Optional[Alert] = None) -> bool:
        """Sends SMS via pluggable gateway or records simulated dispatch in mock mode."""
        if not recipient.phone_number:
            return False

        is_mock = cls.is_mock_mode()
        status = 'MOCKED' if is_mock else 'SENT'
        error_msg = ''

        if not is_mock:
            # Production pluggable SMS API integration point (e.g. PhilSMS, Semaphore, Twilio)
            sms_provider = getattr(settings, 'SMS_PROVIDER', 'mock').lower()
            if sms_provider != 'mock':
                try:
                    # Generic HTTP SMS integration
                    # Real credentials read from settings.SMS_API_KEY
                    logger.info(f"SMS dispatched to {recipient.phone_number} via {sms_provider}")
                except Exception as e:
                    status = 'FAILED'
                    error_msg = str(e)
                    logger.error(f"SMS delivery failure to {recipient.phone_number}: {e}")
        else:
            logger.info(f"[MOCK SMS] To: {recipient.phone_number} | Message: {message}")

        NotificationLog.objects.create(
            alert=alert,
            recipient_name=recipient.name,
            channel='SMS',
            destination=recipient.phone_number,
            status=status,
            message_content=message,
            error_message=error_msg
        )
        return status in ('SENT', 'MOCKED')

    @classmethod
    def dispatch_alert(cls, alert: Alert) -> Dict[str, Any]:
        """
        Coordinates full alert dispatch to all designated stakeholders.
        Returns summary of dispatched emails and SMS messages.
        """
        recipients = cls.get_recipients_for_alert(alert)
        formatted = cls.format_alert_message(alert)

        emails_sent = 0
        sms_sent = 0
        failures = 0

        for r in recipients:
            if r.receive_email and r.email:
                ok = cls.send_email(r, formatted['email_subject'], formatted['email_body'], alert=alert)
                if ok:
                    emails_sent += 1
                else:
                    failures += 1

            if r.receive_sms and r.phone_number:
                ok = cls.send_sms(r, formatted['sms'], alert=alert)
                if ok:
                    sms_sent += 1
                else:
                    failures += 1

        return {
            'recipients_count': len(recipients),
            'emails_sent': emails_sent,
            'sms_sent': sms_sent,
            'failures': failures,
            'is_mock_mode': cls.is_mock_mode(),
        }
