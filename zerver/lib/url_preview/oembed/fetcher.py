import requests
from typing import Dict, Optional
from .provider import ProviderManager

class OEmbedFetcher:
    def __init__(self, provider_manager: ProviderManager):
        self.provider_manager = provider_manager

    def fetch(self, url: str) -> Optional[Dict]:
        provider = self.provider_manager.get_provider(url)
        if not provider:
            return None

        oembed_url = provider.endpoints[0]['url'].format(url=url)
        response = requests.get(oembed_url)
        if response.status_code == 200:
            return response.json()
        return None
