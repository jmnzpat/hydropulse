"""
HydroPulse: Database Seeding Command
Provisions demo users across all RBAC roles, default PNSDW 2017 thresholds,
system settings, sample water sources, and realistic historical water quality records.
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from core.models import (
    User, UserRole, SafetyThreshold, SystemSetting,
    WaterSource, SourceType, WaterQualityRecord, Alert,
    NotificationRecipient, Advisory, AdvisoryType
)
from core.safety_engine import evaluate_water_safety, get_thresholds_from_db


class Command(BaseCommand):
    help = "Seeds the database with RBAC users, PNSDW thresholds, settings, and sample sources"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing HydroPulse database seed..."))

        # 1. System Settings
        self.stdout.write("Configuring system settings...")
        SystemSetting.set_val(
            'ALLOW_HEALTH_OFFICER_DATA_ENTRY',
            'False',
            'Allow Health Officers to input & edit test records'
        )
        SystemSetting.set_val(
            'CAUTION_MARGIN_PERCENT',
            '10.0',
            'Proximity margin percentage for CAUTION status'
        )
        SystemSetting.set_val(
            'NOTIFICATION_MOCK_MODE',
            'True',
            'Simulate email and SMS alerts without sending live external messages'
        )

        # 2. Safety Thresholds (PNSDW 2017 & WHO)
        self.stdout.write("Configuring PNSDW 2017 & WHO safety standards...")
        threshold_data = [
            {
                'parameter_code': 'ph',
                'parameter_name': 'pH Level',
                'unit': 'pH',
                'min_safe': Decimal('6.50'),
                'max_safe': Decimal('8.50'),
                'caution_margin_percent': Decimal('10.00'),
                'standard_reference': 'PNSDW 2017 Table A (Standard: 6.5 - 8.5)',
                'description': 'Measures acidity or basicity. Low pH may cause pipe corrosion; high pH causes bitter taste and scale formation.'
            },
            {
                'parameter_code': 'turbidity',
                'parameter_name': 'Turbidity',
                'unit': 'NTU',
                'min_safe': None,
                'max_safe': Decimal('5.00'),
                'caution_margin_percent': Decimal('10.00'),
                'standard_reference': 'PNSDW 2017 Table B (Max: 5.0 NTU)',
                'description': 'Cloudiness caused by suspended particles; high turbidity shields pathogens from chlorination.'
            },
            {
                'parameter_code': 'tds',
                'parameter_name': 'Total Dissolved Solids (TDS)',
                'unit': 'mg/L',
                'min_safe': None,
                'max_safe': Decimal('600.00'),
                'caution_margin_percent': Decimal('10.00'),
                'standard_reference': 'PNSDW 2017 Table B (Max: 600 mg/L) / WHO',
                'description': 'Total concentration of dissolved minerals and salts. High TDS affects palatability and may indicate runoff contamination.'
            },
        ]

        for t_info in threshold_data:
            code = t_info.pop('parameter_code')
            SafetyThreshold.objects.update_or_create(parameter_code=code, defaults=t_info)

        # 3. RBAC Users
        self.stdout.write("Creating demo RBAC user accounts...")
        users_info = [
            {
                'username': 'admin',
                'password': 'admin12345',
                'email': 'admin@hydropulse.local',
                'first_name': 'Patrick',
                'last_name': 'Jimenez',
                'role': UserRole.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'barangay': 'Central Poblacion',
                'employee_id': 'ADM-2026-001',
                'phone_number': '+639171110001'
            },
            {
                'username': 'engineer',
                'password': 'engr12345',
                'email': 'engineer@hydropulse.local',
                'first_name': 'Christopher',
                'last_name': 'Quizon',
                'role': UserRole.ENGINEER,
                'is_staff': False,
                'barangay': 'San Vicente',
                'employee_id': 'SAN-ENG-042',
                'phone_number': '+639172220002'
            },
            {
                'username': 'health_officer',
                'password': 'health12345',
                'email': 'health@hydropulse.local',
                'first_name': 'Wency',
                'last_name': 'Castillo',
                'role': UserRole.HEALTH_OFFICER,
                'is_staff': False,
                'barangay': 'San Pedro',
                'employee_id': 'MHO-LGU-088',
                'phone_number': '+639173330003'
            },
            {
                'username': 'resident',
                'password': 'resident12345',
                'email': 'resident@hydropulse.local',
                'first_name': 'Maria',
                'last_name': 'Santos',
                'role': UserRole.RESIDENT,
                'is_staff': False,
                'barangay': 'San Vicente',
                'phone_number': '+639174440004'
            },
        ]

        created_users = {}
        for u_data in users_info:
            pwd = u_data.pop('password')
            username = u_data['username']
            user, created = User.objects.get_or_create(username=username, defaults=u_data)
            user.set_password(pwd)
            user.save()
            created_users[username] = user
            status_text = "created" if created else "updated"
            self.stdout.write(f" - {user.username} ({user.get_role_display()}): password set to demo default ({status_text})")

        # 4. Sample Water Sources
        self.stdout.write("Provisioning communal water sources...")
        sources_data = [
            {
                'code': 'SRC-WELL-001',
                'name': 'Purok 1 Communal Deep Well',
                'source_type': SourceType.DEEP_WELL,
                'barangay': 'San Vicente',
                'address_details': 'Near Barangay Health Station and Elementary School',
                'latitude': Decimal('14.599512'),
                'longitude': Decimal('120.984222'),
                'assigned_engineer': created_users['engineer'],
            },
            {
                'code': 'SRC-TAP-002',
                'name': 'Public Market Communal Tap Stand',
                'source_type': SourceType.COMMUNAL_TAP,
                'barangay': 'Central Poblacion',
                'address_details': 'Public Market Perimeter, Stall Gate 2',
                'latitude': Decimal('14.604100'),
                'longitude': Decimal('120.989500'),
                'assigned_engineer': created_users['engineer'],
            },
            {
                'code': 'SRC-SPRING-003',
                'name': 'Sitio Riverside Natural Spring Box',
                'source_type': SourceType.SPRING,
                'barangay': 'San Pedro',
                'address_details': 'Upper Hillside Spring Intake Chamber',
                'latitude': Decimal('14.615200'),
                'longitude': Decimal('120.995100'),
                'assigned_engineer': created_users['engineer'],
            },
            {
                'code': 'SRC-REFILL-004',
                'name': 'AquaPure Community Refilling Station',
                'source_type': SourceType.REFILLING_STATION,
                'barangay': 'San Vicente',
                'address_details': 'Lot 14 Main Highway intersection',
                'latitude': Decimal('14.601000'),
                'longitude': Decimal('120.980000'),
                'assigned_engineer': created_users['engineer'],
            },
            {
                'code': 'SRC-WELL-005',
                'name': 'Barangay Hall Shallow Well',
                'source_type': SourceType.SHALLOW_WELL,
                'barangay': 'Malaya',
                'address_details': 'Behind Multipurpose Evacuation Hall',
                'latitude': Decimal('14.591000'),
                'longitude': Decimal('120.975000'),
                'assigned_engineer': created_users['engineer'],
            },
        ]

        created_sources = []
        for s_data in sources_data:
            code = s_data.pop('code')
            src, _ = WaterSource.objects.update_or_create(code=code, defaults=s_data)
            created_sources.append(src)

        # 5. Notification Recipients
        self.stdout.write("Setting up alert notification recipients...")
        NotificationRecipient.objects.get_or_create(
            name="Dr. Wency Castillo",
            role_title="Municipal Health Officer",
            email="health@hydropulse.local",
            phone_number="+639173330003",
            barangay_filter="",
            receive_email=True,
            receive_sms=True
        )
        NotificationRecipient.objects.get_or_create(
            name="Sanitation Inspector Team",
            role_title="Rural Health Unit Sanitation",
            email="sanitation@hydropulse.local",
            phone_number="+639172220002",
            barangay_filter="San Vicente",
            receive_email=True,
            receive_sms=True
        )

        # 6. Sample Initial Water Quality Tests
        self.stdout.write("Generating sample test records...")
        now = timezone.now()
        thresholds = get_thresholds_from_db()

        # Source 1: Safe clean well
        s1_eval = evaluate_water_safety(ph=7.35, turbidity=1.20, tds=240.0, thresholds=thresholds)
        WaterQualityRecord.objects.get_or_create(
            source=created_sources[0],
            tested_at=now - timedelta(days=1),
            defaults={
                'tested_by': created_users['engineer'],
                'ph_level': Decimal('7.35'),
                'turbidity_ntu': Decimal('1.20'),
                'tds_ppm': Decimal('240.00'),
                'overall_status': s1_eval['overall_status'],
                'failed_parameters': s1_eval['failed_parameters'],
                'notes': 'Routine bi-weekly field test. Water clear and odorless.'
            }
        )

        # Source 2: Caution level (turbidity slightly elevated after rain)
        s2_eval = evaluate_water_safety(ph=6.80, turbidity=4.75, tds=310.0, thresholds=thresholds)
        rec2, _ = WaterQualityRecord.objects.get_or_create(
            source=created_sources[1],
            tested_at=now - timedelta(hours=14),
            defaults={
                'tested_by': created_users['engineer'],
                'ph_level': Decimal('6.80'),
                'turbidity_ntu': Decimal('4.75'),
                'tds_ppm': Decimal('310.00'),
                'overall_status': s2_eval['overall_status'],
                'failed_parameters': s2_eval['failed_parameters'],
                'notes': 'Heavy rainfall in market area. Turbidity approaching threshold (4.75 NTU). Caution flag triggered.'
            }
        )

        # Source 3: Unsafe spring box (high turbidity + alkaline pH)
        s3_eval = evaluate_water_safety(ph=8.80, turbidity=8.40, tds=420.0, thresholds=thresholds)
        rec3, _ = WaterQualityRecord.objects.get_or_create(
            source=created_sources[2],
            tested_at=now - timedelta(hours=4),
            defaults={
                'tested_by': created_users['engineer'],
                'ph_level': Decimal('8.80'),
                'turbidity_ntu': Decimal('8.40'),
                'tds_ppm': Decimal('420.00'),
                'overall_status': s3_eval['overall_status'],
                'failed_parameters': s3_eval['failed_parameters'],
                'notes': 'Runoff sediment intrusion after heavy rain. pH 8.80 and turbidity 8.40 exceed PNSDW limits.'
            }
        )

        # Generate alert for unsafe record 3
        alert3, alert3_created = Alert.objects.get_or_create(
            record=rec3,
            source=created_sources[2],
            defaults={
                'status': 'NEW',
                'severity': 'CRITICAL',
                'summary': 'Turbidity (8.40 NTU) exceeds max 5.0 NTU limit; pH (8.80) exceeds safe range (6.5 - 8.5).'
            }
        )

        # Create active advisory for residents
        Advisory.objects.get_or_create(
            title="Boil Water Notice: Sitio Riverside Natural Spring Box",
            advisory_type=AdvisoryType.BOIL_WATER,
            barangay="San Pedro",
            defaults={
                'summary': "Routine testing on Oct 2 detected elevated turbidity and pH in the Sitio Riverside spring box following heavy rains.",
                'instructions': "All residents drawing water from the Sitio Riverside Spring Box must vigorously boil drinking water for at least 3 minutes or use the designated alternate communal tap stand at the barangay plaza.",
                'is_active': True,
                'published_by': created_users['health_officer'],
            }
        )

        self.stdout.write(self.style.SUCCESS("HydroPulse database seeded successfully!"))
        self.stdout.write("Credentials for demo testing:")
        self.stdout.write("  Administrator:        username='admin'          password='admin12345'")
        self.stdout.write("  Sanitation Engineer:  username='engineer'       password='engr12345'")
        self.stdout.write("  Health Officer / LGU: username='health_officer' password='health12345'")
        self.stdout.write("  Resident:             username='resident'       password='resident12345'")
