from zerver.lib.webhooks.common import get_http_headers_from_filename

key = "HTTP_X_GITHUB_EVENT"
fixture_to_headers = get_http_headers_from_filename(key)
