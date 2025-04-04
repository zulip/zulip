import os
from functools import reduce
from operator import or_

import boto3
import pyvips
from botocore.client import Config
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef, Q

from zerver.lib.partial import partial


def backfill_imageattachment(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ImageAttachment = apps.get_model("zerver", "ImageAttachment")
    Attachment = apps.get_model("zerver", "Attachment")

    if settings.LOCAL_UPLOADS_DIR is None:
        upload_bucket = boto3.resource(
            "s3",
            aws_access_key_id=settings.S3_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            config=Config(
                signature_version=None,
                s3={"addressing_style": settings.S3_ADDRESSING_STYLE},
            ),
        ).Bucket(settings.S3_AUTH_UPLOADS_BUCKET)

    # Historical attachments do not have a mime_type value, so we used
    # to rely on the file extension.  We replicate that when
    # backfilling.  This is the value from zerver.lib.markdown:
    IMAGE_EXTENSIONS = [".bmp", ".gif", ".jpe", ".jpeg", ".jpg", ".png", ".webp"]

    extension_limits = Q()
    extension_limits = reduce(
        or_,
        [Q(file_name__endswith=extension) for extension in IMAGE_EXTENSIONS],
        extension_limits,
    )

    attachments_query = (
        Attachment.objects.alias(
            has_imageattachment=Exists(ImageAttachment.objects.filter(path_id=OuterRef("path_id")))
        )
        .filter(extension_limits, has_imageattachment=False)
        .order_by("id")
    )

    already_processed = 0
    total_to_process = attachments_query.count()
    min_id: int | None = 0
    while True:
        attachments = attachments_query.filter(id__gt=min_id)[:100]

        min_id = None
        for attachment in attachments:
            min_id = attachment.id
            already_processed += 1

            if settings.LOCAL_UPLOADS_DIR is None:
                try:
                    metadata = upload_bucket.Object(attachment.path_id).get()
                except ClientError:
                    print(f"{attachment.path_id}: Missing!")
                    continue

                def s3_read(streamingbody: StreamingBody, size: int) -> bytes:
                    return streamingbody.read(amt=size)

                # We use the streaming body to only pull down as much
                # of the image as we need to examine the headers --
                # generally about 40k
                source: pyvips.Source = pyvips.SourceCustom()
                source.on_read(partial(s3_read, metadata["Body"]))
            else:
                assert settings.LOCAL_FILES_DIR is not None
                attachment_path = os.path.join(settings.LOCAL_FILES_DIR, attachment.path_id)
                if not os.path.exists(attachment_path):
                    print(f"{attachment.path_id}: Missing!")
                    continue
                source = pyvips.Source.new_from_file(attachment_path)
            try:
                image = pyvips.Image.new_from_source(source, "", access="sequential")

                # "original_width_px" and "original_height_px" here are
                # _as rendered_, after applying the orientation
                # information which the image may contain.
                if (
                    "orientation" in image.get_fields()
                    and image.get("orientation") >= 5
                    and image.get("orientation") <= 8
                ):
                    (width, height) = (image.height, image.width)
                else:
                    (width, height) = (image.width, image.height)

                ImageAttachment.objects.create(
                    realm_id=attachment.realm_id,
                    path_id=attachment.path_id,
                    original_width_px=width,
                    original_height_px=height,
                    frames=image.get_n_pages(),
                    thumbnail_metadata=[],
                )
            except pyvips.Error:
                pass

        print(f"Processed {already_processed}/{total_to_process}")
        if min_id is None:
            break


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        # Because this will be backported to 9.x, we only depend on the last migration in 9.x
        ("zerver", "0558_realmuserdefault_web_animate_image_previews_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_imageattachment, reverse_code=migrations.RunPython.noop, elidable=True
        )
    ]
