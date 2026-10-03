"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
app = application

# Serverless auto-initialization on Vercel when running without a permanent DATABASE_URL
if os.getenv('VERCEL') and not os.getenv('DATABASE_URL'):
    try:
        from core.models import User
        if not User.objects.exists():
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            call_command('seed_data')
    except Exception:
        try:
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            call_command('seed_data')
        except Exception as e:
            print(f"Vercel DB auto-init exception: {e}")

