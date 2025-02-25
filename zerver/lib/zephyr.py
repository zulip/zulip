import re
import traceback

import dns.resolver


def compute_mit_user_fullname(email: str) -> str:
    try:
        # Input is either e.g. username@mit.edu or user|CROSSREALM.INVALID@mit.edu
        match_user = re.match(r"^([a-zA-Z0-9_.-]+)(\|.+)?@mit\.edu$", email.lower())
        if match_user and match_user.group(2) is None:
            answer = dns.resolver.resolve(f"{match_user.group(1)}.passwd.ns.athena.mit.edu", "TXT")
            hesiod_name = answer[0].strings[0].decode().split(":")[4].split(",")[0].strip()
            if hesiod_name != "":
                return hesiod_name
        elif match_user:
            return match_user.group(1).lower() + "@" + match_user.group(2).upper().removeprefix("|")
    except dns.resolver.NXDOMAIN:
        pass
    except Exception:
        print(f"Error getting fullname for {email}:")
        traceback.print_exc()
    return email.lower()
