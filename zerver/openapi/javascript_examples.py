import os
import subprocess

from zulip import Client

def test_js_bindings(client: Client) -> None:
    '''
        TODO:
            Make sure all expected functions were called.
            Make sure docs work.
            from zerver.openapi.openapi import validate_against_openapi_schema

        {
            f: 'send_message',
            endpoint: '/messages',
            method 'post',
        },
        {
            f: 'create_user',
            endpoint: '/users',
            method: 'post',
        },
    '''
    os.environ['ZULIP_USERNAME'] = client.email
    os.environ['ZULIP_API_KEY'] = client.api_key
    os.environ['ZULIP_REALM'] = client.base_url[:-5]

    responses_str = subprocess.check_output(
        args=['node', 'zerver/openapi/js_examples.js'],
        universal_newlines=True,
    );
    print('JS finished!!!!!!!!!!!!!')
    print(responses_str)
