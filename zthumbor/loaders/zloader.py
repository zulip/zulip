# See https://zulip.readthedocs.io/en/latest/subsystems/thumbnailing.html

import base64
import logging
import urllib.parse

from tc_aws.loaders import s3_loader
from thumbor.context import Context
from thumbor.loaders import LoaderResult, file_loader, https_loader

from .helpers import (
    THUMBOR_EXTERNAL_TYPE,
    THUMBOR_LOCAL_FILE_TYPE,
    THUMBOR_S3_TYPE,
    separate_url_and_source_type,
)


def get_not_found_result() -> LoaderResult:
    result = LoaderResult()
    result.error = LoaderResult.ERROR_NOT_FOUND
    result.successful = False
    return result

async def load(context: Context, url: str) -> LoaderResult:
    source_type, encoded_url = separate_url_and_source_type(url)
    actual_url = base64.urlsafe_b64decode(urllib.parse.unquote(encoded_url)).decode('utf-8')

    if source_type == THUMBOR_S3_TYPE:
        if actual_url.startswith('/user_uploads/'):
            actual_url = actual_url[len('/user_uploads/'):]
        else:
            raise AssertionError("Unexpected s3 file.")

        return await s3_loader.load(context, actual_url)
    elif source_type == THUMBOR_LOCAL_FILE_TYPE:
        if actual_url.startswith('/user_uploads/'):
            actual_url = actual_url[len('/user_uploads/'):]
            local_file_path_prefix = 'files/'
        else:
            raise AssertionError("Unexpected local file.")

        patched_local_url = local_file_path_prefix + actual_url
        return await file_loader.load(context, patched_local_url)
    elif source_type == THUMBOR_EXTERNAL_TYPE:
        return await https_loader.load(context, actual_url)
    else:
        logging.warning('INVALID SOURCE TYPE: ' + source_type)
        return get_not_found_result()
