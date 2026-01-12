#!/usr/bin/env python3
"""
Quick diagnostic script to check Celery setup
"""
import sys
from app.celery_app import celery_app
from app.core.config import get_settings

settings = get_settings()

print("=" * 60)
print("🔍 Celery Diagnostic Check")
print("=" * 60)

# Check Redis connection
print("\n1. Checking Redis connection...")
try:
    from redis import Redis
    redis_client = Redis.from_url(settings.REDIS_URL)
    redis_client.ping()
    print("   ✅ Redis is accessible")
except Exception as e:
    print(f"   ❌ Redis connection failed: {e}")
    print("   Please ensure Redis is running and REDIS_URL is correct")
    sys.exit(1)

# Check Celery broker
print("\n2. Checking Celery broker...")
try:
    inspect = celery_app.control.inspect()
    active_workers = inspect.active()
    if active_workers:
        print(f"   ✅ Celery workers are running: {list(active_workers.keys())}")
    else:
        print("   ⚠️  No active Celery workers found")
        print("   Please start Celery worker with:")
        print("   celery -A app.celery_app worker --loglevel=info")
except Exception as e:
    print(f"   ⚠️  Could not check workers: {e}")

# Check Twilio credentials
print("\n3. Checking Twilio credentials...")
if settings.TWILIO_ACCOUNT_SID:
    print(f"   ✅ TWILIO_ACCOUNT_SID is set: {settings.TWILIO_ACCOUNT_SID[:10]}...")
else:
    print("   ❌ TWILIO_ACCOUNT_SID is not set")

if settings.TWILIO_AUTH_TOKEN:
    print(f"   ✅ TWILIO_AUTH_TOKEN is set: {'*' * 20}")
else:
    print("   ❌ TWILIO_AUTH_TOKEN is not set")

if settings.TWILIO_WHATSAPP_NUMBER:
    print(f"   ✅ TWILIO_WHATSAPP_NUMBER is set: {settings.TWILIO_WHATSAPP_NUMBER}")
else:
    print("   ❌ TWILIO_WHATSAPP_NUMBER is not set")

# Test sending a message
print("\n4. Testing Twilio service...")
try:
    from app.services.integrations.twilio_service import TwilioIntegrationService
    service = TwilioIntegrationService()
    print("   ✅ Twilio service initialized")
except Exception as e:
    print(f"   ❌ Failed to initialize Twilio service: {e}")

print("\n" + "=" * 60)
print("✅ Diagnostic complete")
print("=" * 60)
