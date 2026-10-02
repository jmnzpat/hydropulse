"""
HydroPulse: Core Application URL Configuration
Phases 1-4 routes: Auth, Water Sources, Records, Dashboard, Alerts & Notifications.
"""

from django.urls import path
from core import views_auth, views_water, views_dashboard, views_alerts

app_name = 'core'

urlpatterns = [
    # ----------------------------------------------------------------
    # Phase 1: Authentication & RBAC User Management
    # ----------------------------------------------------------------
    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout'),
    path('profile/', views_auth.profile_view, name='profile'),
    path('profile/password/', views_auth.password_change_view, name='password_change'),

    path('admin/users/', views_auth.user_list_view, name='user_list'),
    path('admin/users/create/', views_auth.user_create_view, name='user_create'),
    path('admin/users/<int:user_id>/edit/', views_auth.user_edit_view, name='user_edit'),
    path('admin/users/<int:user_id>/toggle-status/', views_auth.user_toggle_status_view, name='user_toggle_status'),

    path('admin/settings/', views_auth.system_settings_view, name='system_settings'),
    path('admin/audit-logs/', views_auth.audit_logs_view, name='audit_logs'),

    # ----------------------------------------------------------------
    # Phase 2: Water Sources Management
    # ----------------------------------------------------------------
    path('sources/', views_water.source_list_view, name='source_list'),
    path('sources/create/', views_water.source_create_view, name='source_create'),
    path('sources/<int:source_id>/', views_water.source_detail_view, name='source_detail'),
    path('sources/<int:source_id>/edit/', views_water.source_edit_view, name='source_edit'),
    path('sources/<int:source_id>/toggle-status/', views_water.source_toggle_status_view, name='source_toggle_status'),

    # Phase 2: Water Quality Records & Evaluation
    path('records/', views_water.record_list_view, name='record_list'),
    path('records/create/', views_water.record_create_view, name='record_create'),
    path('records/<int:record_id>/', views_water.record_detail_view, name='record_detail'),
    path('records/<int:record_id>/edit/', views_water.record_edit_view, name='record_edit'),
    path('records/<int:record_id>/delete/', views_water.record_delete_view, name='record_delete'),
    path('records/<int:record_id>/restore/', views_water.record_restore_view, name='record_restore'),

    # Phase 2: Safety Thresholds (Admin)
    path('admin/standards/', views_water.threshold_list_view, name='threshold_list'),
    path('admin/standards/<int:threshold_id>/edit/', views_water.threshold_edit_view, name='threshold_edit'),

    # Phase 2: Live Evaluation API Preview
    path('api/evaluate-preview/', views_water.api_evaluate_preview, name='api_evaluate_preview'),

    # ----------------------------------------------------------------
    # Phase 3: Dashboard & Analytics Visualizations
    # ----------------------------------------------------------------
    path('dashboard/', views_dashboard.dashboard_view, name='dashboard'),
    path('api/dashboard-charts/', views_dashboard.api_dashboard_charts, name='api_dashboard_charts'),

    # ----------------------------------------------------------------
    # Phase 4: Automated Alerts & Notification System
    # ----------------------------------------------------------------
    # Alert lifecycle (list, detail, acknowledge, resolve)
    path('alerts/', views_alerts.alert_list_view, name='alert_list'),
    path('alerts/<int:alert_id>/', views_alerts.alert_detail_view, name='alert_detail'),
    path('alerts/<int:alert_id>/acknowledge/', views_alerts.alert_acknowledge_view, name='alert_acknowledge'),
    path('alerts/<int:alert_id>/resolve/', views_alerts.alert_resolve_view, name='alert_resolve'),

    # Notification recipients registry (Admin)
    path('admin/notifications/recipients/', views_alerts.notification_recipient_list_view, name='notification_recipients'),
    path('admin/notifications/recipients/add/', views_alerts.notification_recipient_create_view, name='notification_recipient_create'),
    path('admin/notifications/recipients/<int:recipient_id>/edit/', views_alerts.notification_recipient_edit_view, name='notification_recipient_edit'),
    path('admin/notifications/recipients/<int:recipient_id>/toggle/', views_alerts.notification_recipient_toggle_view, name='notification_recipient_toggle'),
    path('admin/notifications/recipients/<int:recipient_id>/test/', views_alerts.notification_test_send_view, name='notification_test_send'),

    # Notification transmission audit log
    path('admin/notifications/logs/', views_alerts.notification_log_list_view, name='notification_logs'),

    # ----------------------------------------------------------------
    # Phases 5-6 Placeholders (public portal & reports — coming soon)
    # ----------------------------------------------------------------
    path('', views_alerts.alert_list_view, name='public_portal'),   # temporary redirect to alerts until Phase 5
    path('reports/', views_dashboard.dashboard_view, name='report_dashboard'),    # placeholder
    path('advisories/', views_dashboard.dashboard_view, name='advisory_list'),    # placeholder
]
