import re
from typing import Dict

# Warning: If you change this parsing, please test using
#   zerver/tests/test_decorators.py
# And extend zerver/tests/fixtures/user_agents_unique with any new test cases
pattern = re.compile(
    r"""^ (?P<name> [^/ ]* [^0-9/(]* )
    (/ (?P<version> [^/ ]* ))?
    ([ /] .*)?
    $""",
    re.X,
)


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    match = pattern.match(user_agent)
    assert match is not None
    return match.groupdict()
