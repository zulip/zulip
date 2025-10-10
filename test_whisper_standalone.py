#!/usr/bin/env python3
"""
Standalone test script for whisper functionality.
This script tests the whisper models and logic without requiring a full Django setup.
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Add the zulip directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'zerver',
        ],
        SECRET_KEY='test-secret-key',
        USE_TZ=True,
    )

django.setup()

# Now we can import Django models
from django.test import TestCase
from django.contrib.auth.models import User
from zerver.models.whispers import (
    WhisperConversation,
    WhisperParticipant,
    WhisperRequest,
    get_whisper_participants_hash,
    get_active_whisper_conversation,
)

def test_whisper_hash_generation():
    """Test whisper participant hash generation"""
    print("Testing whisper hash generation...")
    
    # Test hash consistency
    user_ids1 = [1, 2, 3]
    user_ids2 = [3, 1, 2]
    
    hash1 = get_whisper_participants_hash(user_ids1)
    hash2 = get_whisper_participants_hash(user_ids2)
    
    assert hash1 == hash2, f"Hashes should be equal: {hash1} != {hash2}"
    assert len(hash1) == 40, f"Hash should be 40 characters long, got {len(hash1)}"
    
    print("✓ Hash generation test passed")

def test_whisper_models():
    """Test whisper model creation"""
    print("Testing whisper model structure...")
    
    # Test that models can be imported and have expected attributes
    assert hasattr(WhisperConversation, 'parent_recipient')
    assert hasattr(WhisperConversation, 'participants_hash')
    assert hasattr(WhisperConversation, 'is_active')
    
    assert hasattr(WhisperRequest, 'requester')
    assert hasattr(WhisperRequest, 'recipient')
    assert hasattr(WhisperRequest, 'status')
    
    assert hasattr(WhisperParticipant, 'whisper_conversation')
    assert hasattr(WhisperParticipant, 'user_profile')
    assert hasattr(WhisperParticipant, 'is_active')
    
    print("✓ Model structure test passed")

def test_whisper_status_choices():
    """Test whisper request status choices"""
    print("Testing whisper request status choices...")
    
    assert WhisperRequest.Status.PENDING == 1
    assert WhisperRequest.Status.ACCEPTED == 2
    assert WhisperRequest.Status.DECLINED == 3
    assert WhisperRequest.Status.EXPIRED == 4
    
    print("✓ Status choices test passed")

def run_basic_tests():
    """Run basic tests that don't require database"""
    print("Running basic whisper functionality tests...\n")
    
    try:
        test_whisper_hash_generation()
        test_whisper_models()
        test_whisper_status_choices()
        
        print("\n🎉 All basic tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_whisper_feature_info():
    """Display information about the whisper feature"""
    print("=" * 60)
    print("WHISPER CHAT FEATURE IMPLEMENTATION")
    print("=" * 60)
    print()
    print("📋 COMPLETED COMPONENTS:")
    print("  ✅ Database Models (WhisperConversation, WhisperRequest, WhisperParticipant)")
    print("  ✅ Core Management Logic (create, join, leave conversations)")
    print("  ✅ Request System (send, accept, decline whisper invitations)")
    print("  ✅ Permission Validation (access control and security)")
    print("  ✅ Rate Limiting (spam prevention)")
    print("  ✅ Cleanup Functions (expired requests, inactive conversations)")
    print()
    print("🔧 NEXT STEPS TO COMPLETE:")
    print("  🔲 REST API Endpoints")
    print("  🔲 Real-time Events")
    print("  🔲 Frontend UI Components")
    print("  🔲 Integration with Zulip's message system")
    print()
    print("📁 FILES CREATED:")
    print("  • zulip/zerver/models/whispers.py - Whisper data models")
    print("  • zulip/zerver/lib/whispers.py - Core whisper logic")
    print("  • zulip/zerver/migrations/0754_add_whisper_models.py - Database migration")
    print("  • zulip/zerver/tests/test_whispers.py - Model tests")
    print("  • zulip/zerver/tests/test_whisper_lib.py - Logic tests")
    print("  • zulip/zerver/tests/test_whisper_requests.py - Request system tests")
    print()
    print("🧪 TESTING OPTIONS:")
    print("  1. Run this script: python test_whisper_standalone.py")
    print("  2. Set up Zulip dev environment and run: ./tools/test-backend zerver.tests.test_whispers")
    print("  3. Manual testing via Django shell (after setting up environment)")
    print()

if __name__ == "__main__":
    show_whisper_feature_info()
    
    print("🧪 Running basic functionality tests...")
    print("-" * 40)
    
    success = run_basic_tests()
    
    if success:
        print("\n💡 NEXT STEPS:")
        print("1. Set up the full Zulip development environment to run complete tests")
        print("2. Apply the database migration: python manage.py migrate")
        print("3. Run the full test suite: ./tools/test-backend zerver.tests.test_whispers")
        print("4. Continue with API endpoint implementation (Task 4)")
    else:
        print("\n🔧 Please check the implementation and fix any issues before proceeding.")