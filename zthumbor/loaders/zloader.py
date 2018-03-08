from __future__ import absolute_import

from six.moves import urllib
from tornado.concurrent import return_future
from thumbor.loaders import LoaderResult, file_loader, https_loader
from tc_aws.loaders import s3_loader
from thumbor.context import Context
from .helpers import (
    separate_url_and_source_type,
    THUMBOR_S3_TYPE, THUMBOR_LOCAL_FILE_TYPE, THUMBOR_EXTERNAL_TYPE
)

from typing import Any, Callable

import base64
import logging

def get_not_found_result():
    # type: () -> LoaderResult
    result = LoaderResult()
    result.error = LoaderResult.ERROR_NOT_FOUND
    result.successful = False
    return result

@return_future
def load(context, url, callback):
    # type: (Context, str, Callable[..., Any]) -> None
    source_type, encoded_url = separate_url_and_source_type(url)
    actual_url = base64.urlsafe_b64decode(urllib.parse.unquote(encoded_url))
    if source_type not in (THUMBOR_S3_TYPE, THUMBOR_LOCAL_FILE_TYPE,
                           THUMBOR_EXTERNAL_TYPE):
        callback(get_not_found_result())
        logging.warning('INVALID SOURCE TYPE: ' + source_type)
        return

    if source_type == THUMBOR_S3_TYPE:
        s3_loader.load(context, actual_url, callback)
    elif source_type == THUMBOR_LOCAL_FILE_TYPE:
        patched_local_url = 'files/' + actual_url  # type: ignore # python 2 type differs from python 3 type
        file_loader.load(context, patched_local_url, callback)
    elif source_type == THUMBOR_EXTERNAL_TYPE:
        https_loader.load(context, actual_url, callback)
