from typing import MutableMapping, Any
from django.conf import settings

def get_fixed_content_for_widget(content: str) -> str:
    if not settings.ALLOW_SUB_MESSAGES:
        return content

    if content == '/stats':
        return 'We are running **1 server**.'

    return content

def do_widget_post_save_actions(message: MutableMapping[str, Any]) -> None:
    '''
    This is experimental code that only works with the
    webapp for now.
    '''
    if not settings.ALLOW_SUB_MESSAGES:
        return
