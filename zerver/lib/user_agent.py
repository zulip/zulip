import re
from typing import Optional, Dict

# Warning: If you change this parsing, please test using
#   zerver/tests/test_decorators.py
# And extend zerver/fixtures/user_agents_unique with any new test cases
def parse_user_agent(user_agent):
    # type: (str) -> Optional[Dict[str, str]]
    match = re.match("^(?P<name>[^/ ]*[^0-9/(]*)(/(?P<version>[^/ ]*))?([ /].*)?$", user_agent)
    if match is None:
        return None
    return match.groupdict()
