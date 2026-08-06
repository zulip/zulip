import os
import tempfile

from django.core.files.uploadhandler import TemporaryFileUploadHandler
from typing_extensions import override

# Django spools each uploaded file to a temporary file named
# f"{tempfile.gettempprefix()}{8 random characters}.upload{extension}",
# where the extension is taken verbatim from the client-provided filename.
#
# Since a filename is limited to NAME_MAX (255) bytes, a sufficiently
# long extension makes creating that temporary file fail with
# 'OSError: [Errno 36] File name too long', which Django does not handle.
TEMPORARY_FILE_MAX_EXTENSION_LENGTH = 255 - len(tempfile.gettempprefix()) - 8 - len(".upload")


def truncate_filename_extension(filename: str) -> str:
    """Shortens filename extensions that are too long to fit in the name of
    the temporary file Django spools an upload to. NAME_MAX limits bytes
    rather than characters, so we truncate the encoded extension and discard
    any character left partially encoded at the end.
    """
    root, extension = os.path.splitext(filename)
    encoded_extension = extension.encode()
    if len(encoded_extension) <= TEMPORARY_FILE_MAX_EXTENSION_LENGTH:
        return filename
    return root + encoded_extension[:TEMPORARY_FILE_MAX_EXTENSION_LENGTH].decode(errors="ignore")


class ZulipTemporaryFileUploadHandler(TemporaryFileUploadHandler):
    """Django's TemporaryFileUploadHandler, made tolerant of filenames whose
    extension alone exceeds what the filesystem allows in a filename.

    Django does sanitize an over-long filename, in UploadedFile._set_name,
    but only after creating the temporary file whose name embeds the
    extension; shortening the extension is therefore something we have to do
    beforehand. The cap is far longer than any extension in practice.
    """

    @override
    def new_file(
        self,
        field_name: str,
        file_name: str,
        content_type: str,
        content_length: int | None,
        charset: str | None = None,
        content_type_extra: dict[str, bytes] | None = None,
    ) -> None:
        super().new_file(
            field_name,
            truncate_filename_extension(file_name),
            content_type,
            content_length,
            charset,
            content_type_extra,
        )
