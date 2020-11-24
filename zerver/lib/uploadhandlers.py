import logging
import os
from typing import Any, Callable, Dict, List, Optional, Union

import botocore
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.files.uploadhandler import FileUploadHandler, StopFutureHandlers
from django.http import HttpRequest
from django.utils.translation import ugettext as _

from zerver.lib.upload import (
    check_upload_within_quota,
    create_attachment,
    get_file_info,
    get_s3_client,
    is_file_upload_request,
    upload_backend,
)

logger = logging.getLogger(__name__)

class UploadFileSizeLimitExceeded(Exception):
    pass

class UploadError(Exception):
    pass

class S3File(UploadedFile):
    def __init__(self, name: str, request: HttpRequest, content_type: Optional[str]=None, size: Optional[int]=None, charset: Optional[str]=None,
                 content_type_extra: Optional[Dict[Any, Any]]=None) -> None:
        self.path = upload_backend.get_target_file_path(name, request.user.realm)
        super().__init__(None, name, content_type, size, charset, content_type_extra)

class LocalFile(UploadedFile):
    def __init__(self, name: str, request: HttpRequest, content_type: Optional[str]=None, size: Optional[int]=None, charset: Optional[str]=None,
                 content_type_extra: Optional[Dict[Any, Any]]=None) -> None:
        self.path = upload_backend.get_target_file_path(name, request.user.realm)
        self.absolute_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "files", self.path)
        os.makedirs(os.path.dirname(self.absolute_path), exist_ok=True)
        file = open(self.absolute_path, "wb+")

        super().__init__(file, name, content_type, size, charset, content_type_extra)

    def close(self) -> None:
        try:
            self.file.close()
        except FileNotFoundError:  # nocoverage
            pass
class UserFileUploadHandler(FileUploadHandler):
    def handle_raw_input(self, input_data: HttpRequest, META: Dict[Any, Any], content_length: int, boundary: str, encoding: Optional[str]=None) -> None:
        if not is_file_upload_request(self.request):
            self.activated = False
            return

        self.activated = True
        if settings.MAX_FILE_UPLOAD_SIZE * 1024 * 1024 < content_length:
            raise UploadFileSizeLimitExceeded(_("Uploaded file is larger than the allowed limit of {} MiB").format(
                settings.MAX_FILE_UPLOAD_SIZE,
            ))
        check_upload_within_quota(self.request.user.realm, content_length)

        self.file: Optional[Union[S3File, LocalFile]] = None
        self.file_completed = False

        self.GENERIC_ERROR_MESSAGE = _("Error while uploading the file. Please try again.")

def catch_errors(func: Callable[..., Optional[Union[S3File, bytes]]]) -> Callable[..., Optional[Union[S3File, bytes]]]:
    def _catch_errors(self: UserFileUploadHandler, *args: Any, **kwargs: Any) -> Optional[Union[S3File, bytes]]:
        try:
            return func(self, *args, **kwargs)
        except botocore.exceptions.ClientError:
            logger.error("Error during S3 multipart file upload")
            self.s3_upload_errored = True
            if func.__name__ == "file_complete":
                return self.file
            return None
        except StopFutureHandlers:
            raise
    return _catch_errors

class S3FileUploadHandler(UserFileUploadHandler):
    @catch_errors
    def new_file(self, field_name: str, file_name: str, content_type: str, content_length: int, charset: Optional[str]=None,
                 content_type_extra: Optional[Dict[Any, Any]]=None) -> None:
        if not self.activated:
            return

        cleaned_file_name: str
        self.s3_upload_errored = False
        self.mpu = {}

        cleaned_file_name, content_type = get_file_info(self.request, file_name)
        super().new_file(field_name, cleaned_file_name, content_type, content_length, charset, content_type_extra)
        self.file = S3File(self.file_name, self.request, self.content_type, 0, self.charset, self.content_type_extra)
        self.bucket = settings.S3_AUTH_UPLOADS_BUCKET
        self.s3 = get_s3_client()
        metadata = {
            "user_profile_id": str(self.request.user.id),
            "realm_id": str(self.request.user.realm_id),
        }
        self.mpu = self.s3.create_multipart_upload(
            Bucket=self.bucket, Key=self.file.path, Metadata=metadata, ContentType=content_type
        )
        self.multipart_content = bytearray()
        self.multiparts: List[Dict[str, Any]] = []
        self.multipart_number = 0

        raise StopFutureHandlers()

    @catch_errors
    def receive_data_chunk(self, raw_data: bytes, start: int) -> Optional[bytes]:
        if not self.activated:
            return raw_data

        if self.s3_upload_errored or not self.file:
            return None

        self.multipart_content.extend(raw_data)

        INITIAL_MULITIPARTS_MIN_SIZE = 5 * 1024 * 1024
        if len(self.multipart_content) > INITIAL_MULITIPARTS_MIN_SIZE:
            self.multipart_number += 1

            multipart = self.s3.upload_part(Bucket=self.bucket, Key=self.file.path, PartNumber=self.multipart_number,
                                            UploadId=self.mpu['UploadId'], Body=self.multipart_content)
            self.multiparts.append({
                "PartNumber":  self.multipart_number,
                "ETag": multipart["ETag"]
            })
            self.multipart_content = bytearray()

        return None

    @catch_errors
    def file_complete(self, file_size: int) -> Optional[S3File]:
        if not self.activated or not self.file:
            return None

        if self.s3_upload_errored:
            return self.file

        if self.multipart_content:
            self.multipart_number += 1
            multipart = self.s3.upload_part(Bucket=self.bucket, Key=self.file.path, PartNumber=self.multipart_number,
                                            UploadId=self.mpu['UploadId'], Body=self.multipart_content)
            self.multiparts.append({
                "PartNumber":  self.multipart_number,
                "ETag": multipart["ETag"]
            })

        part_info = {}
        part_info["Parts"] = self.multiparts
        self.s3.complete_multipart_upload(Bucket=self.bucket, Key=self.file.path, UploadId=self.mpu['UploadId'],
                                          MultipartUpload=part_info)
        create_attachment(self.file.name, self.file.path, self.request.user, file_size)
        self.file_completed = True
        return self.file

    def upload_complete(self) -> None:
        if not self.activated or not self.file:
            return

        if not self.s3_upload_errored and self.file_completed:
            return

        if self.mpu:
            try:
                self.s3.abort_multipart_upload(
                    Bucket=self.bucket,
                    Key=self.file.path,
                    UploadId=self.mpu['UploadId'],
                )
            except botocore.exceptions.ClientError:
                logger.error("Error while aborting S3 multipart file upload")
                pass

        raise UploadError(self.GENERIC_ERROR_MESSAGE)

class LocalFileUploadHandler(UserFileUploadHandler):
    def new_file(self, field_name: str, file_name: str, content_type: str, content_length: int, charset: Optional[str]=None,
                 content_type_extra: Optional[Dict[Any, Any]]=None) -> None:
        if not self.activated:
            return

        cleaned_file_name, _ = get_file_info(self.request, file_name)
        super().new_file(field_name, cleaned_file_name, content_type, content_length, charset, content_type_extra)
        self.file = LocalFile(self.file_name, self.request, self.content_type, 0, self.charset, self.content_type_extra)
        raise StopFutureHandlers()

    def receive_data_chunk(self, raw_data: bytes, start: int) -> Optional[bytes]:
        if not self.activated or not self.file:
            return raw_data
        self.file.write(raw_data)
        return None

    def file_complete(self, file_size: int) -> Optional[LocalFile]:
        if not self.activated or not self.file:
            return None

        self.file.seek(0)
        self.file.size = file_size
        create_attachment(self.file.name, self.file.path, self.request.user, file_size)
        self.file_completed = True
        return self.file

    def upload_complete(self) -> None:
        if not self.activated or not self.file:
            return

        if self.file_completed:
            return

        try:
            os.remove(self.file.absolute_path)
        except FileNotFoundError:  # nocoverage
            pass
        raise UploadError(self.GENERIC_ERROR_MESSAGE)

if settings.LOCAL_UPLOADS_DIR is not None:
    ZulipUserFileUploadHandler: Any  = LocalFileUploadHandler
else:
    ZulipUserFileUploadHandler = S3FileUploadHandler  # nocoverage
