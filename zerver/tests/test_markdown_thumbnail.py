import re
from unittest.mock import patch

import pyvips
from typing_extensions import override

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import re_thumbnail
from zerver.actions.message_send import check_message, do_send_messages
from zerver.lib.addressee import Addressee
from zerver.lib.camo import get_camo_url
from zerver.lib.markdown import render_message_markdown
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import read_test_image_file
from zerver.lib.thumbnail import ThumbnailFormat
from zerver.lib.upload import upload_message_attachment
from zerver.models import (
    ArchivedAttachment,
    ArchivedMessage,
    Attachment,
    Client,
    ImageAttachment,
    Message,
)
from zerver.models.clients import get_client
from zerver.models.realms import get_realm
from zerver.worker.thumbnail import ensure_thumbnails


class MarkdownThumbnailTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        self.login("othello")
        super().setUp()

    def assert_message_content_is(
        self, message_id: int, rendered_content: str, user_name: str = "othello"
    ) -> None:
        sender_user_profile = self.example_user(user_name)
        result = self.assert_json_success(
            self.api_get(sender_user_profile, f"/api/v1/messages/{message_id}")
        )
        self.assertEqual(result["message"]["content"], rendered_content)

    def send_message_content(
        self, content: str, do_thumbnail: bool = False, user_name: str = "othello"
    ) -> int:
        sender_user_profile = self.example_user(user_name)
        return self.send_stream_message(
            sender=sender_user_profile,
            stream_name="Verona",
            content=content,
            skip_capture_on_commit_callbacks=not do_thumbnail,
        )

    def test_uploads_preview_order(self) -> None:
        image_names = ["img.jpg", "img.png", "img.gif"]
        path_ids = [self.upload_and_thumbnail_image(image_name) for image_name in image_names]
        content = (
            f"Test 1\n[{image_names[0]}](/user_uploads/{path_ids[0]}) \n\n"
            f"Next image\n[{image_names[1]}](/user_uploads/{path_ids[1]}) \n\n"
            f"Another screenshot\n[{image_names[2]}](/user_uploads/{path_ids[2]})"
        )

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, content)
        self.assertEqual(
            converted.rendered_content,
            (
                "<p>Test 1<br>\n"
                f'<a href="/user_uploads/{path_ids[0]}">{image_names[0]}</a> </p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_ids[0]}" title="{image_names[0]}">'
                "<img"
                ' data-original-content-type="image/jpeg"'
                ' data-original-dimensions="128x128"'
                f' src="/user_uploads/thumbnail/{path_ids[0]}/840x560.webp"></a></div>'
                "<p>Next image<br>\n"
                f'<a href="/user_uploads/{path_ids[1]}">{image_names[1]}</a> </p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_ids[1]}" title="{image_names[1]}">'
                "<img"
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                f' src="/user_uploads/thumbnail/{path_ids[1]}/840x560.webp"></a></div>'
                "<p>Another screenshot<br>\n"
                f'<a href="/user_uploads/{path_ids[2]}">{image_names[2]}</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_ids[2]}" title="{image_names[2]}">'
                "<img"
                ' data-original-content-type="image/gif"'
                ' data-original-dimensions="128x128"'
                f' src="/user_uploads/thumbnail/{path_ids[2]}/840x560.webp"></a></div>'
            ),
        )

    def test_thumbnail_code_block(self) -> None:
        url = "http://example.com/image.png"
        path_id = self.upload_and_thumbnail_image("img.png")
        # We have a path_id of an image in the message content, so we
        # will prefetch the thumbnail metadata -- but not insert it.

        sender_user_profile = self.example_user("othello")
        msg = Message(
            sender=sender_user_profile,
            sending_client=get_client("test"),
            realm=sender_user_profile.realm,
        )
        converted = render_message_markdown(msg, f"{url}\n```\n/user_uploads/{path_id}\n```")
        self.assertEqual(
            converted.rendered_content,
            (
                f'<div class="message_inline_image"><a href="{url}"><img src="{get_camo_url(url)}"></a></div>'
                f'<div class="codehilite"><pre><span></span><code>/user_uploads/{path_id}\n'
                "</code></pre></div>"
            ),
        )

    def test_thumbnail_after_send(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            path_id = self.upload_image("img.png")
            content = f"[image](/user_uploads/{path_id})"
            expected = (
                f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
            )

            message_id = self.send_message_content(content)
            self.assert_message_content_is(message_id, expected)

            # Exit the block and run thumbnailing
        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_inline_image_thumbnail_after_send(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            path_id = self.upload_image("img.png")
            content = f"![image](/user_uploads/{path_id})"
            expected = (
                '<p><img alt="image"'
                ' class="message_inline_image image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                f' data-original-src="/user_uploads/{path_id}"'
                ' src="/static/images/loading/loader-black.svg"></p>'
            )

            message_id = self.send_message_content(content)
            self.assert_message_content_is(message_id, expected)

            # Exit the block and run thumbnailing
        expected = (
            '<p><img alt="image" class="true_inline"'
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' data-original-src="/user_uploads/{path_id}"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></p>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_thumbnail_escaping(self) -> None:
        self.login("othello")
        with self.captureOnCommitCallbacks(execute=True):
            url = upload_message_attachment(
                "I am 95% ± 5% certain!",
                "image/png",
                read_test_image_file("img.png"),
                self.example_user("othello"),
            )[0]
            path_id = re.sub(r"/user_uploads/", "", url)
            self.assertTrue(ImageAttachment.objects.filter(path_id=path_id).exists())
        message_id = self.send_message_content(f"[I am 95% ± 5% certain!](/user_uploads/{path_id})")
        expected = (
            f'<p><a href="/user_uploads/{path_id}">I am 95% ± 5% certain!</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="I am 95% ± 5% certain!">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_thumbnail_repeated(self) -> None:
        # We currently have no way to generate a thumbnailing event
        # for the worker except during upload, meaning that we will
        # never repeat a ImageAttachment thumbnailing.  However, the
        # code supports it, so test it.

        # Thumbnail with one set of sizes
        with self.thumbnail_formats(
            ThumbnailFormat("webp", 100, 75, animated=True),
            ThumbnailFormat("webp", 100, 75, animated=False),
        ):
            path_id = self.upload_and_thumbnail_image("animated_unequal_img.gif")
            content = f"[animated_unequal_img.gif](/user_uploads/{path_id})"
            expected = (
                f'<p><a href="/user_uploads/{path_id}">animated_unequal_img.gif</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="animated_unequal_img.gif">'
                '<img data-animated="true"'
                ' data-original-content-type="image/gif"'
                ' data-original-dimensions="128x56"'
                f' src="/user_uploads/thumbnail/{path_id}/100x75-anim.webp"></a></div>'
            )
            message_id = self.send_message_content(content, do_thumbnail=True)
        self.assert_message_content_is(message_id, expected)
        self.assert_length(ImageAttachment.objects.get(path_id=path_id).thumbnail_metadata, 2)

        # Re-thumbnail with a non-overlapping set of sizes
        with self.thumbnail_formats(ThumbnailFormat("jpg", 100, 75, animated=False)):
            ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))

        # We generate a new size but leave the old ones
        self.assert_length(ImageAttachment.objects.get(path_id=path_id).thumbnail_metadata, 3)

        # And the contents are not updated to the new size
        self.assert_message_content_is(message_id, expected)

    def test_thumbnail_sequential_edits(self) -> None:
        first_path_id = self.upload_image("img.png")
        second_path_id = self.upload_image("img.jpg")

        message_id = self.send_message_content(
            f"[first image](/user_uploads/{first_path_id})\n[second image](/user_uploads/{second_path_id})",
            do_thumbnail=False,
        )
        self.assert_message_content_is(
            message_id,
            (
                f'<p><a href="/user_uploads/{first_path_id}">first image</a><br>\n'
                f'<a href="/user_uploads/{second_path_id}">second image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{first_path_id}" title="first image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
                f'<div class="message_inline_image"><a href="/user_uploads/{second_path_id}" title="second image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/jpeg"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
            ),
        )

        # Complete thumbnailing the second image first -- replacing only that spinner
        ensure_thumbnails(ImageAttachment.objects.get(path_id=second_path_id))
        self.assert_message_content_is(
            message_id,
            (
                f'<p><a href="/user_uploads/{first_path_id}">first image</a><br>\n'
                f'<a href="/user_uploads/{second_path_id}">second image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{first_path_id}" title="first image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
                f'<div class="message_inline_image"><a href="/user_uploads/{second_path_id}" title="second image">'
                "<img"
                ' data-original-content-type="image/jpeg"'
                ' data-original-dimensions="128x128"'
                f' src="/user_uploads/thumbnail/{second_path_id}/840x560.webp"></a></div>'
            ),
        )

        # Finish the other thumbnail
        ensure_thumbnails(ImageAttachment.objects.get(path_id=first_path_id))
        self.assert_message_content_is(
            message_id,
            (
                f'<p><a href="/user_uploads/{first_path_id}">first image</a><br>\n'
                f'<a href="/user_uploads/{second_path_id}">second image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{first_path_id}" title="first image">'
                "<img"
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                f' src="/user_uploads/thumbnail/{first_path_id}/840x560.webp"></a></div>'
                f'<div class="message_inline_image"><a href="/user_uploads/{second_path_id}" title="second image">'
                "<img"
                ' data-original-content-type="image/jpeg"'
                ' data-original-dimensions="128x128"'
                f' src="/user_uploads/thumbnail/{second_path_id}/840x560.webp"></a></div>'
            ),
        )

    def test_thumbnail_of_deleted(self) -> None:
        sender_user_profile = self.example_user("othello")
        path_id = self.upload_image("img.png")
        message_id = self.send_message_content(f"[image](/user_uploads/{path_id})")

        # Delete the message
        do_delete_messages(
            sender_user_profile.realm, [Message.objects.get(id=message_id)], acting_user=None
        )

        # There is still an ImageAttachment row
        self.assertFalse(Attachment.objects.filter(path_id=path_id).exists())
        self.assertTrue(ArchivedAttachment.objects.filter(path_id=path_id).exists())
        self.assertTrue(ImageAttachment.objects.filter(path_id=path_id).exists())

        # Completing rendering after it is deleted should work, and
        # update the rendered content in the archived message
        ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))
        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assertEqual(
            ArchivedMessage.objects.get(id=message_id).rendered_content,
            expected,
        )
        # See test_delete_unclaimed_attachments for tests of the
        # archiving process itself, and how it interacts with
        # thumbnails.

    def test_thumbnail_bad_image(self) -> None:
        """Test what happens if the file looks fine, but resizing later fails"""
        path_id = self.upload_image("img.png")
        message_id = self.send_message_content(f"[image](/user_uploads/{path_id})")
        self.assert_length(ImageAttachment.objects.get(path_id=path_id).thumbnail_metadata, 0)

        # If the image is found to be bad, we remove all trace of the preview
        with (
            patch.object(
                pyvips.Image, "thumbnail_buffer", side_effect=pyvips.Error("some bad error")
            ) as thumb_mock,
            self.assertLogs("zerver.worker.thumbnail", "ERROR") as thumbnail_logs,
        ):
            ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))
            thumb_mock.assert_called_once()
        self.assert_length(thumbnail_logs.output, 1)
        self.assertTrue(
            thumbnail_logs.output[0].startswith("ERROR:zerver.worker.thumbnail:some bad error")
        )
        self.assertFalse(ImageAttachment.objects.filter(path_id=path_id).exists())
        self.assert_message_content_is(
            message_id, f'<p><a href="/user_uploads/{path_id}">image</a></p>'
        )

    def test_thumbnail_bad_inline_image(self) -> None:
        """Test what happens if the file looks fine, but resizing later fails"""
        path_id = self.upload_image("img.png")
        message_id = self.send_message_content(f"Testing ![image](/user_uploads/{path_id})")
        self.assert_length(ImageAttachment.objects.get(path_id=path_id).thumbnail_metadata, 0)

        # If the image is found to be bad, we remove all trace of the preview
        with (
            patch.object(
                pyvips.Image, "thumbnail_buffer", side_effect=pyvips.Error("some bad error")
            ) as thumb_mock,
            self.assertLogs("zerver.worker.thumbnail", "ERROR") as thumbnail_logs,
        ):
            ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))
            thumb_mock.assert_called_once()
        self.assert_length(thumbnail_logs.output, 1)
        self.assertTrue(
            thumbnail_logs.output[0].startswith("ERROR:zerver.worker.thumbnail:some bad error")
        )
        self.assertFalse(ImageAttachment.objects.filter(path_id=path_id).exists())
        self.assert_message_content_is(message_id, "<p>Testing </p>")

    def test_thumbnail_multiple_messages(self) -> None:
        sender_user_profile = self.example_user("othello")
        path_id = self.upload_image("img.png")
        channel_message_id = self.send_message_content(f"A public [image](/user_uploads/{path_id})")
        private_message_id = self.send_personal_message(
            from_user=sender_user_profile,
            to_user=self.example_user("hamlet"),
            content=f"This [image](/user_uploads/{path_id}) is private",
            skip_capture_on_commit_callbacks=True,
        )
        placeholder = (
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            '<img class="image-loading-placeholder"'
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            ' src="/static/images/loading/loader-black.svg"></a></div>'
        )
        self.assert_message_content_is(
            channel_message_id,
            f'<p>A public <a href="/user_uploads/{path_id}">image</a></p>\n{placeholder}',
        )

        self.assert_message_content_is(
            private_message_id,
            f'<p>This <a href="/user_uploads/{path_id}">image</a> is private</p>\n{placeholder}',
        )

        with (
            patch.object(
                pyvips.Image, "thumbnail_buffer", wraps=pyvips.Image.thumbnail_buffer
            ) as thumb_mock,
            self.thumbnail_formats(
                ThumbnailFormat("webp", 100, 75, animated=False),
                ThumbnailFormat("webp", 200, 150, animated=False),
            ),
        ):
            ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))

        # Called once per format
        self.assertEqual(thumb_mock.call_count, 2)

        rendered_thumb = (
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/100x75.webp"></a></div>'
        )

        self.assert_message_content_is(
            channel_message_id,
            f'<p>A public <a href="/user_uploads/{path_id}">image</a></p>\n{rendered_thumb}',
        )

        self.assert_message_content_is(
            private_message_id,
            f'<p>This <a href="/user_uploads/{path_id}">image</a> is private</p>\n{rendered_thumb}',
        )

    def test_thumbnail_race(self) -> None:
        """Test what happens when thumbnailing happens between rendering and sending"""
        path_id = self.upload_image("img.png")

        self.assert_length(ImageAttachment.objects.get(path_id=path_id).thumbnail_metadata, 0)

        # Render, but do not send, the message referencing the image.
        # This will render as a spinner, since the thumbnail has not
        # been generated yet.
        send_request = check_message(
            self.example_user("othello"),
            Client.objects.get_or_create(name="test suite")[0],
            Addressee.for_stream_name("Verona", "test"),
            f"[image](/user_uploads/{path_id})",
        )
        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            '<img class="image-loading-placeholder"'
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            ' src="/static/images/loading/loader-black.svg"></a></div>'
        )
        self.assertEqual(send_request.message.rendered_content, expected)

        # Thumbnail the image.  The message does not exist yet, so
        # nothing is re-written.
        ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))

        # Send the message; this should re-check the ImageAttachment
        # data, find the thumbnails, and update the rendered_content
        # to no longer contain a spinner.
        message_id = do_send_messages([send_request])[0].message_id

        rendered_thumb = (
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(
            message_id, f'<p><a href="/user_uploads/{path_id}">image</a></p>\n{rendered_thumb}'
        )

    def test_thumbnail_historical_image(self) -> None:
        # Note that this is outside the captureOnCommitCallbacks, so
        # we don't actually run thumbnailing for it.  This results in
        # a ImageAttachment row but no thumbnails, which matches the
        # state of backfilled previously-uploaded images.
        path_id = self.upload_image("img.png")

        with self.captureOnCommitCallbacks(execute=True):
            message_id = self.send_message_content(f"An [image](/user_uploads/{path_id})")

            content = f"[image](/user_uploads/{path_id})"
            expected = (
                f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
            )

            message_id = self.send_message_content(content)
            self.assert_message_content_is(message_id, expected)

        # Exiting the block should have run the thumbnailing that was
        # enqueued when rendering the message.
        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_thumbnail_transcode(self) -> None:
        path_id = self.upload_image("img.tif")
        message_id = self.send_message_content(
            f"An [image](/user_uploads/{path_id})", do_thumbnail=True
        )
        expected = (
            f'<p>An <a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/tiff"'
            ' data-original-dimensions="128x128"'
            ' data-transcoded-image="4032x3024.webp"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_re_thumbnail_stuck(self) -> None:
        # For the case when we generated a thumbnail, but there was a
        # race condition in updating the message, which left it with a
        # permanent spinner.  No new thumbnailing is enqueued.
        with self.captureOnCommitCallbacks(execute=True):
            path_id = self.upload_image("img.png")
            content = f"[image](/user_uploads/{path_id})"
            expected = (
                f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
            )

            message_id = self.send_message_content(content)
            self.assert_message_content_is(message_id, expected)

            # Exit the block and run thumbnailing

        # Set the rendered content back to the spinner version, so
        # simulate one of the race condition bugs we have had in the
        # past
        self.assertEqual(
            Message.objects.filter(
                realm_id=get_realm("zulip").id,
                has_image=True,
                rendered_content__contains='class="image-loading-placeholder"',
            ).count(),
            0,
        )
        message = Message.objects.get(id=message_id)
        message.rendered_content = expected
        message.save()
        self.assertEqual(
            Message.objects.filter(
                realm_id=get_realm("zulip").id,
                has_image=True,
                rendered_content__contains='class="image-loading-placeholder"',
            ).count(),
            1,
        )

        # Trigger the re-thumbnailing codepath
        re_thumbnail(Message, message_id, enqueue=False)

        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_re_thumbnail_historical(self) -> None:
        # Note that this is all outside the captureOnCommitCallbacks,
        # so we don't actually run thumbnailing for it.  This results
        # in a ImageAttachment row but no thumbnails, which matches
        # the state of backfilled previously-uploaded images.
        path_id = self.upload_image("img.png")

        # We don't execute callbacks at all, to drop thumbnailing
        # which would have been done
        content = f"[image](/user_uploads/{path_id})"
        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            '<img class="image-loading-placeholder"'
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            ' src="/static/images/loading/loader-black.svg"></a></div>'
        )

        message_id = self.send_message_content(content)
        self.assert_message_content_is(message_id, expected)

        # Force-update to the version without thumbnails
        self.assertEqual(
            Message.objects.filter(
                realm_id=get_realm("zulip").id,
                has_image=True,
                rendered_content__contains='<img src="/user_uploads/',
            )
            .exclude(rendered_content__contains='<img src="/user_uploads/thumbnail/')
            .count(),
            0,
        )
        message = Message.objects.get(id=message_id)
        message.rendered_content = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            f'<img src="/user_uploads/{path_id}"></a></div>'
        )
        message.save()
        self.assertEqual(
            Message.objects.filter(
                realm_id=get_realm("zulip").id,
                has_image=True,
                rendered_content__contains='<img src="/user_uploads/',
            )
            .exclude(rendered_content__contains='<img src="/user_uploads/thumbnail/')
            .count(),
            1,
        )

        with self.captureOnCommitCallbacks(execute=True):
            # Trigger the re-thumbnailing codepath
            re_thumbnail(Message, message_id, enqueue=True)

            # It should have a spinner
            self.assert_message_content_is(message_id, expected)

            # ...and exiting the block should trigger the thumbnailing worker

        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

        # Calling re_thumbnail on the message does nothing if it has a thumbnail
        with self.captureOnCommitCallbacks(execute=True):
            re_thumbnail(Message, message_id, enqueue=True)
            self.assert_message_content_is(message_id, expected)
        self.assert_message_content_is(message_id, expected)

    def test_re_thumbnail_historical_archivedmessage(self) -> None:
        # As above, no worker is run, so we get no thumbnails.
        path_id = self.upload_image("img.png")
        message_id = self.send_message_content(f"[image](/user_uploads/{path_id})")

        # Force-update to the version without thumbnails
        sender_user_profile = self.example_user("othello")
        message = Message.objects.get(id=message_id)
        message.rendered_content = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            f'<img src="/user_uploads/{path_id}"></a></div>'
        )
        message.save()

        # Delete the message
        do_delete_messages(
            sender_user_profile.realm, [Message.objects.get(id=message_id)], acting_user=None
        )

        with self.captureOnCommitCallbacks(execute=True):
            # Trigger the re-thumbnailing codepath
            re_thumbnail(ArchivedMessage, message_id, enqueue=True)

            # It should have a spinner
            expected = (
                f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
                f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
                '<img class="image-loading-placeholder"'
                ' data-original-content-type="image/png"'
                ' data-original-dimensions="128x128"'
                ' src="/static/images/loading/loader-black.svg"></a></div>'
            )
            self.assertEqual(
                ArchivedMessage.objects.get(id=message_id).rendered_content,
                expected,
            )

            # ...and exiting the block should trigger the thumbnailing worker

        expected = (
            f'<p><a href="/user_uploads/{path_id}">image</a></p>\n'
            f'<div class="message_inline_image"><a href="/user_uploads/{path_id}" title="image">'
            "<img"
            ' data-original-content-type="image/png"'
            ' data-original-dimensions="128x128"'
            f' src="/user_uploads/thumbnail/{path_id}/840x560.webp"></a></div>'
        )
        self.assertEqual(
            ArchivedMessage.objects.get(id=message_id).rendered_content,
            expected,
        )
