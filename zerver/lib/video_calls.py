import requests
import jwt
from typing import Any, Dict, Optional
import time

def request_zoom_video_call_url(user_id: str, api_key: str, api_secret: str) -> Optional[Dict[str, Any]]:
    encodedToken = jwt.encode({
        'iss': api_key,
        'exp': int(round(time.time() * 1000)) + 5000
    }, api_secret, algorithm='HS256').decode('utf-8')

    response = requests.post(
        'https://api.zoom.us/v2/users/' + user_id + '/meetings',
        headers = {
            'Authorization': 'Bearer ' + encodedToken,
            'content-type': 'application/json'
        },
        json = {}
    )

    try:
        response.raise_for_status()
    except Exception:
        return None

    return response.json()
