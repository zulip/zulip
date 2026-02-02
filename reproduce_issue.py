
import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

# Mock django settings
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True)

try:
    from zerver.lib.webhooks.git import EMOJI_AWARD_MESSAGE_TEMPLATE
    print(f"Template: {EMOJI_AWARD_MESSAGE_TEMPLATE}")
except ImportError as e:
    print(f"ImportError in git.py: {e}")
    sys.exit(1)

try:
    from zerver.webhooks.gitlab.view import get_emoji_event_body
    print("Imported get_emoji_event_body")
except ImportError as e:
    print(f"ImportError in view.py: {e}")
    sys.exit(1)

# Mock payload
payload = {
  "object_kind": "emoji",
  "event_type": "award",
  "user": {
    "name": "Administrator",
    "username": "root",
  },
  "project_id": 1,
  "object_attributes": {
    "user_id": 1,
    "name": "smile",
    "awardable_type": "Issue",
    "awardable_id": 1
  },
  "issue": {
    "iid": 1,
    "title": "Ut commodi ullam eos dolores perferendis nihil sunt.",
    "url": "http://example.com/gitlab-org/gitlab-test/issues/1"
  }
}

# Mock WildValue
class WildValue:
    def __init__(self, value):
        self._value = value

    def __getitem__(self, key):
        if isinstance(self._value, dict) and key in self._value:
            return WildValue(self._value[key])
        raise KeyError(key)
    
    def get(self, key, default=None):
        if isinstance(self._value, dict):
            val = self._value.get(key, default)
            if val is None: return None
            return WildValue(val)
        return None

    def __contains__(self, key):
        return key in self._value

    def tame(self, validator):
        return self._value

# Simple check_string/check_int mocks
def check_string(val): return str(val)
def check_int(val): return int(val)

# Patch view.py imports to use our mocks? 
# It's hard to patch imports inside the module. 
# Instead, we just rely on the fact that WildValue in view.py 
# is imported from zerver.lib.validator.

# We will try to run the logic of get_emoji_event_body directly if we can't invoke it.
# Actually, since we can't easily mock WildValue in view.py without proper environment, 
# checking imports is the most important step here.

print("Imports successful.")
