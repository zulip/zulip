import json
import re
from typing import Dict, List, Optional

class OEmbedProvider:
    def __init__(self, provider_name: str, provider_url: str, endpoints: List[Dict[str, any]]):
        self.provider_name = provider_name
        self.provider_url = provider_url
        self.endpoints = endpoints

class ProviderManager:
    def __init__(self):
        self.providers: List[OEmbedProvider] = []

    def load_providers(self, providers_data: List[Dict[str, any]]) -> None:
        for provider_data in providers_data:
            provider = OEmbedProvider(
                provider_name=provider_data['provider_name'],
                provider_url=provider_data['provider_url'],
                endpoints=provider_data['endpoints']
            )
            self.providers.append(provider)

    def get_provider(self, url: str) -> Optional[OEmbedProvider]:
        for provider in self.providers:
            for endpoint in provider.endpoints:
                if 'schemes' in endpoint:
                    for scheme in endpoint['schemes']:
                        if re.match(self._convert_scheme_to_regex(scheme), url):
                            return provider
        return None

    def _convert_scheme_to_regex(self, scheme: str) -> str:
        return '^' + re.escape(scheme).replace('\\*', '.*') + '$'

# Example usage:
providers_json = '''
[
    {
        "provider_name": "23HQ",
        "provider_url": "http://www.23hq.com",
        "endpoints": [
            {
                "schemes": [
                    "http://www.23hq.com/*/photo/*"
                ],
                "url": "http://www.23hq.com/23/oembed"
            }
        ]
    },
    {
        "provider_name": "YouTube",
        "provider_url": "https://www.youtube.com/",
        "endpoints": [
            {
                "schemes": [
                    "https://youtube.com/watch*",
                    "https://www.youtube.com/watch*",
                    "https://youtu.be/*",
                    "https://youtube.com/playlist?list=*",
                    "https://www.youtube.com/playlist?list=*"
                ],
                "url": "https://www.youtube.com/oembed",
                "discovery": true
            }
        ]
    }
]
'''

# Create and initialize the ProviderManager
provider_manager = ProviderManager()
providers_data = json.loads(providers_json)
provider_manager.load_providers(providers_data)

# Test the get_provider method
test_urls = [
    "http://www.23hq.com/user123/photo/1234567",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://example.com/not-supported"
]

for url in test_urls:
    provider = provider_manager.get_provider(url)
    if provider:
        print(f"Provider found for {url}: {provider.provider_name}")
    else:
        print(f"No provider found for {url}")
