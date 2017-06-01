from six.moves import urllib
from tornado.concurrent import return_future
from thumbor.loaders import LoaderResult, file_loader, http_loader
from tc_aws.loaders import s3_loader
from . import helpers

from typing import Any, Callable


def get_not_found_result():
    # type: () -> LoaderResult
    result = LoaderResult()
    result.error = LoaderResult.ERROR_NOT_FOUND
    result.successful = False
    return result


@return_future
def load(context, url, callback):
    # type: (Any, str, Callable) -> None
    # TODO: Fix type of 'context'
    url = urllib.parse.unquote(url)
    if not helpers.sign_is_valid(url, context):
        callback(get_not_found_result())
        return
    url_params = helpers.get_url_params(url)
    if not helpers.is_external_url(url):
        url = urllib.parse.urlsplit(url).path
    source_type = url_params.get('source_type')
    if source_type == helpers.THUMBOR_S3_TYPE:
        s3_loader.load(context, url, callback)
    elif source_type == helpers.THUMBOR_LOCAL_FILE_TYPE:
        file_loader.load(context, url, callback)
    elif source_type == helpers.THUMBOR_EXTERNAL_TYPE:
        http_loader.load_sync(
            context,
            url,
            callback,
            normalize_url_func=http_loader._normalize_url)
    else:
        callback(get_not_found_result())
