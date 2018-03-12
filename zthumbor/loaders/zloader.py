from __future__ import absolute_import

from six.moves import urllib
from tornado.concurrent import return_future
from thumbor.loaders import LoaderResult, file_loader, http_loader
from tc_aws.loaders import s3_loader
from thumbor.context import Context
from .helpers import (
    get_url_params, sign_is_valid, THUMBOR_S3_TYPE, THUMBOR_LOCAL_FILE_TYPE,
    THUMBOR_EXTERNAL_TYPE
)

from typing import Any, Callable

def get_not_found_result():
    # type: () -> LoaderResult
    result = LoaderResult()
    result.error = LoaderResult.ERROR_NOT_FOUND
    result.successful = False
    return result

@return_future
def load(context, url, callback):
    # type: (Context, str, Callable[..., Any]) -> None
    url = urllib.parse.unquote(url)
    url_params = get_url_params(url)
    source_type = url_params.get('source_type')

    if not sign_is_valid(url, context) or source_type not in (
            THUMBOR_S3_TYPE, THUMBOR_LOCAL_FILE_TYPE, THUMBOR_EXTERNAL_TYPE):
        callback(get_not_found_result())
        return

    url = url.rsplit('?', 1)[0]
    if source_type == THUMBOR_S3_TYPE:
        s3_loader.load(context, url, callback)
    elif source_type == THUMBOR_LOCAL_FILE_TYPE:
        file_loader.load(context, url, callback)
    elif source_type == THUMBOR_EXTERNAL_TYPE:
        http_loader.load_sync(
            context,
            url,
            callback,
            normalize_url_func=http_loader._normalize_url)
