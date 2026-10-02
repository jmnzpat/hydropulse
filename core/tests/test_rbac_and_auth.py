"""
Unit and Integration Tests for HydroPulse RBAC & Authentication
Validates user permissions, dynamic setting toggles, route protection, and audit logging.
"""

import pytest
from django.test import Client
from django.urls import reverse
from core.models import User, UserRole, SystemSetting, AuditLog
from core import rbac


@pytest.mark.django_db
class TestRBACPermissions:

    def setup_method(self):
        self.admin = User.objects.create_user(
            username='test_admin', password='password123', role=UserRole.ADMIN
        )
        self.engineer = User.objects.create_user(
            username='test_engineer', password='password123', role=UserRole.ENGINEER
        )
        self.health_officer = User.objects.create_user(
            username='test_health', password='password123', role=UserRole.HEALTH_OFFICER
        )
        self.resident = User.objects.create_user(
            username='test_resident', password='password123', role=UserRole.RESIDENT
        )

    def test_admin_permissions(self):
        assert rbac.is_admin(self.admin) is True
        assert rbac.can_input_records(self.admin) is True
        assert rbac.can_manage_sources(self.admin) is True
        assert rbac.can_manage_alerts(self.admin) is True
        assert rbac.can_manage_users(self.admin) is True

    def test_sanitation_engineer_permissions(self):
        assert rbac.is_sanitation_engineer(self.engineer) is True
        assert rbac.is_admin(self.engineer) is False
        assert rbac.can_input_records(self.engineer) is True
        assert rbac.can_manage_sources(self.engineer) is True
        assert rbac.can_manage_users(self.engineer) is False

    def test_health_officer_data_entry_toggle(self):
        """
        Tests the student proposal nuance:
        Default: Health Officer cannot encode data.
        When ALLOW_HEALTH_OFFICER_DATA_ENTRY is True, Health Officer CAN encode data.
        """
        SystemSetting.set_val('ALLOW_HEALTH_OFFICER_DATA_ENTRY', 'False')
        assert rbac.can_input_records(self.health_officer) is False

        SystemSetting.set_val('ALLOW_HEALTH_OFFICER_DATA_ENTRY', 'True')
        assert rbac.can_input_records(self.health_officer) is True

    def test_resident_restricted_permissions(self):
        assert rbac.can_input_records(self.resident) is False
        assert rbac.can_manage_sources(self.resident) is False
        assert rbac.can_manage_alerts(self.resident) is False
        assert rbac.can_manage_users(self.resident) is False


@pytest.mark.django_db
class TestRouteProtection:

    def setup_method(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_user', password='password123', role=UserRole.ADMIN
        )
        self.engineer = User.objects.create_user(
            username='engr_user', password='password123', role=UserRole.ENGINEER
        )

    def test_anonymous_access_redirected(self):
        response = self.client.get(reverse('core:user_list'))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_engineer_cannot_access_admin_user_list(self):
        self.client.login(username='engr_user', password='password123')
        response = self.client.get(reverse('core:user_list'))
        assert response.status_code == 302
        assert reverse('core:dashboard') in response.url

    def test_admin_can_access_user_list(self):
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(reverse('core:user_list'))
        assert response.status_code == 200
        assert 'User & Role Management' in response.content.decode()


@pytest.mark.django_db
class TestAuditLogging:

    def test_audit_log_creation(self):
        user = User.objects.create_user(
            username='audited_user', password='password123', role=UserRole.ADMIN
        )
        from core.audit import log_audit
        log = log_audit(
            request=None,
            action="SYSTEM_INIT",
            module="AUTH",
            record_id="1",
            details="Seeded initial system user",
            user=user
        )
        assert log.id is not None
        assert log.action == "SYSTEM_INIT"
        assert log.module == "AUTH"
        assert AuditLog.objects.filter(action="SYSTEM_INIT").exists()
