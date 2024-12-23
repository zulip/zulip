from typing import Dict, Optional
import time

class OEmbedCache:
    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Dict] = {}
        self.ttl = ttl

    def get(self, url: str) -> Optional[Dict]:
        if url in self.cache:
            data, timestamp = self.cache[url]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[url]
        return None

    def set(self, url: str, data: Dict) -> None:
        self.cache[url] = (data, time.time())
