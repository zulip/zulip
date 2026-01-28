import sys
from contextlib import ExitStack, redirect_stdout
from email.message import EmailMessage
from typing import Literal, TextIO

import boto3
import botocore.exceptions
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.utils.http import content_disposition_header

INLINE_MIME_TYPES = [
    # AUDIO_INLINE_MIME_TYPES
    "audio/aac",
    "audio/flac",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/webm",
    # Image and video types
    "application/pdf",
    "image/apng",
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
    "video/mp4",
    "video/webm",
    # This list should not be added to in the future -- rather,
    # consider if a new migration is warranted, or if old uploads of
    # the new type should be left as attachments.
]


def bare_content_type(content_type: str) -> str:
    fake_msg = EmailMessage()
    fake_msg["content-type"] = content_type
    return fake_msg.get_content_type()


def update_s3_metadata(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    if settings.LOCAL_UPLOADS_DIR is not None:
        return

    assert settings.S3_AUTH_UPLOADS_BUCKET
    checksum: Literal["when_required", "when_supported"] = (
        "when_required" if settings.S3_SKIP_CHECKSUM else "when_supported"
    )
    bucket = boto3.resource(
        "s3",
        aws_access_key_id=settings.S3_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        endpoint_url=settings.S3_ENDPOINT_URL,
        config=Config(
            signature_version=None,
            s3={"addressing_style": settings.S3_ADDRESSING_STYLE},
            request_checksum_calculation=checksum,
        ),
    ).Bucket(settings.S3_AUTH_UPLOADS_BUCKET)

    with ExitStack() as stack:
        if settings.PRODUCTION:
            log_file: TextIO = stack.enter_context(
                open("/var/log/zulip/migrations_0757_s3_metadata.log", "w")
            )
        else:
            log_file = sys.stderr
            print(file=log_file)
        stack.enter_context(redirect_stdout(log_file))

        Attachment = apps.get_model("zerver", "Attachment")
        all_attachments = Attachment.objects.all().order_by("id")
        attachments_count = all_attachments.count()

        for i, attachment in enumerate(all_attachments.iterator()):
            if i % 100 == 0:
                print(f"... {i} / {attachments_count} = {(100 * i / attachments_count):5.2f}")
            s3_object = bucket.Object(attachment.path_id)
            try:
                s3_object.load()
            except botocore.exceptions.ClientError:
                print(f"!! {attachment.path_id} does not exist")
                print()
                continue

            # Find out if we need to pull data from S3 back into the database (for really old attachments)
            changed: set[str] = set()
            if str(attachment.create_time) < "1980-01-01":
                # Some very early attachments have '1979-12-31 00:00:00+00'
                if not changed:
                    print(f">> {attachment.path_id}:")
                print(f"  create_time:  {attachment.create_time}")
                print(f"             -> {s3_object.last_modified}")
                attachment.create_time = s3_object.last_modified
                changed.add("create_time")
            if attachment.content_type is None:
                # We didn't use to record the content-type in the database
                if "/" in s3_object.content_type:
                    content_type = s3_object.content_type
                elif "%2f" in s3_object.content_type.lower():
                    # An early bug caused 'image%2fpng'
                    content_type = s3_object.content_type.lower().replace("%2f", "/")
                else:
                    content_type = "application/octet-stream"
                if not changed:
                    print(f">> {attachment.path_id}:")
                print("  content_type: None")
                print(f"             -> {content_type}")
                attachment.content_type = content_type
                changed.add("content_type")
            if changed:
                attachment.save(update_fields=list(changed))
                print()

            # Recalculate metadata and headers in S3, based on database
            metadata = {
                "realm-id": str(attachment.realm_id),
                "user-profile-id": str(attachment.owner_id),
            }
            content_type = attachment.content_type
            is_attachment = bare_content_type(content_type) not in INLINE_MIME_TYPES
            content_disposition = (
                content_disposition_header(is_attachment, attachment.file_name) or "attachment"
            )

            if s3_object.metadata != metadata:
                pass
            elif s3_object.content_type != content_type:
                pass
            elif s3_object.content_disposition != content_disposition:
                pass
            elif s3_object.storage_class != settings.S3_UPLOADS_STORAGE_CLASS:
                pass
            else:
                continue

            print(f"<< {attachment.path_id}:")
            print(f" @ {attachment.create_time}")
            if s3_object.metadata != metadata:
                print(f"  Metadata:     {s3_object.metadata}")
                print(f"             -> {metadata}")
            elif s3_object.content_type != content_type:
                print(f"  Content-type: {s3_object.content_type}")
                print(f"             -> {content_type}")
            elif s3_object.content_disposition != content_disposition:
                print(f"  Disposition:  {s3_object.content_disposition}")
                print(f"             -> {content_disposition}")
            elif s3_object.storage_class != settings.S3_UPLOADS_STORAGE_CLASS:
                print(f"  StorageClass: {s3_object.storage_class}")
                print(f"             -> {settings.S3_UPLOADS_STORAGE_CLASS}")
            print()

            s3_object.copy_from(
                ContentType=content_type,
                ContentDisposition=content_disposition,
                CopySource={"Bucket": settings.S3_AUTH_UPLOADS_BUCKET, "Key": attachment.path_id},
                Metadata=metadata,
                MetadataDirective="REPLACE",
                StorageClass=settings.S3_UPLOADS_STORAGE_CLASS,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0763_migrate_realms_using_y_rating_to_use_a_g_rating_for_giphy"),
    ]

    operations = [
        migrations.RunPython(update_s3_metadata, elidable=True),
    ]
