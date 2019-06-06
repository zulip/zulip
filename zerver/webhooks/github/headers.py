from typing import Dict

def fixture_to_headers(filename: str) -> Dict[str, str]:
    if '__' in filename:
        event_type = filename.split("__")[0]
    else:
        event_type = filename
    return {"HTTP_X_GITHUB_EVENT": event_type}
