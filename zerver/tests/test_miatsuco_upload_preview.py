from zerver.lib.markdown import render_message_markdown
from zerver.lib.test_miatsuco import MiatsucoMarkdownTestMixin
from zerver.models import ImageAttachment, Message
from zerver.models.realms import get_realm


class MiatsucoUploadPreviewVideoAudioTest(MiatsucoMarkdownTestMixin):
    def test_inline_audio_preview_unaffected_by_miatsuco_upload_preview_setting(self) -> None:
        # miatsuco_inline_upload_preview only controls image/video previews;
        # audio always embeds as a player regardless of this
        # setting.
        realm = self.example_user("othello").realm
        realm.miatsuco_inline_upload_preview = False
        realm.save()

        url, path_id = self.upload_file_and_get_path_id("filename", "audio/mpeg")
        message_id = self.send_message_content(f"![Audio link](/user_uploads/{path_id})")
        expected = (
            f'<p><audio controls preload="metadata" src="{url}" title="Audio link"></audio></p>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_inline_video_preview(self) -> None:
        # Test video previews with a valid uploaded video file.
        # Unlike images, uploaded video previews are not backed by
        # a database-verified path id; is_video() relies on
        # MIME-type sniffing of the URL alone.
        url, path_id = self.upload_file_and_get_path_id("filename.mp4", "video/mp4")
        message_id = self.send_message_content(f"[Video link](/user_uploads/{path_id})")
        # A plain link to a video renders the link text as a paragraph,
        # with the inline video preview appended below it (matching how
        # upstream renders any plain link to a video file).
        expected = (
            f'<p><a href="{url}">Video link</a></p>\n'
            f'<div class="message_inline_image message_inline_video">'
            f'<a href="{url}" title="Video link">'
            f'<video preload="metadata" src="{url}"></video></a></div>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_inline_video_preview_disabled(self) -> None:
        realm = self.example_user("othello").realm
        realm.miatsuco_inline_upload_preview = False
        realm.save()

        url, path_id = self.upload_file_and_get_path_id("filename.mp4", "video/mp4")
        message_id = self.send_message_content(f"[Video link](/user_uploads/{path_id})")
        # With the setting off, we fall back to a plain link instead
        # of an inline <video> preview.
        expected = f'<p><a href="{url}">Video link</a></p>'
        self.assert_message_content_is(message_id, expected)


class MiatsucoUploadPreviewImageTest(MiatsucoMarkdownTestMixin):
    def test_miatsuco_inline_upload_preview_disabled(self) -> None:
        self.login("othello")
        realm = get_realm("zulip")
        realm.miatsuco_inline_upload_preview = False
        realm.save()

        with self.captureOnCommitCallbacks(execute=True):
            path_id = self.upload_image("img.png")
            content = f"![image](/user_uploads/{path_id})"

            # With the setting off, we fall back to a plain link,
            # never showing a loading placeholder either.
            expected = f'<p><a href="/user_uploads/{path_id}">image</a></p>'
            message_id = self.send_message_content(content)
            self.assert_message_content_is(message_id, expected)

            # Exit the block and run thumbnailing.

        # Thumbnailing still happened in the background, independent
        # of whether the preview is displayed.
        self.assertTrue(ImageAttachment.objects.filter(path_id=path_id).exists())
        image_attachment = ImageAttachment.objects.get(path_id=path_id)
        self.assertIsNotNone(image_attachment.thumbnail_metadata)

        # The rendered message content is unaffected by the
        # thumbnail now being ready, since we never rendered a
        # placeholder for rewrite_thumbnailed_images to find.
        self.assert_message_content_is(message_id, expected)

        # Turning the setting back on affects future renders (e.g.
        # after an edit), not retroactively across old renders.
        realm.miatsuco_inline_upload_preview = True
        realm.save()
        msg = Message.objects.get(id=message_id)
        rendered = render_message_markdown(msg, content)
        self.assertIn('class="inline-image"', rendered.rendered_content)
        self.assertIn(f"/user_uploads/thumbnail/{path_id}/840x560.webp", rendered.rendered_content)

    def test_miatsuco_inline_upload_preview_disabled_with_link_preview_enabled(self) -> None:
        # Regression test: uploaded-image previews must stay off
        # when miatsuco_inline_upload_preview is disabled, even though our
        # ImageInlineProcessor fallback turns the ![]() syntax into
        # a plain <a> link, and InlineInterestingLinkProcessor could
        # otherwise resurrect a preview for that link based on
        # inline_image_preview alone. is_image() checks
        # miatsuco_upload_preview_enabled independently for uploaded files,
        # regardless of inline_image_preview's value.
        self.login("othello")
        realm = get_realm("zulip")
        self.assertTrue(realm.inline_image_preview)
        realm.miatsuco_inline_upload_preview = False
        realm.save()

        with self.captureOnCommitCallbacks(execute=True):
            path_id = self.upload_image("img.png")
            content = f"![image](/user_uploads/{path_id})"
            expected = f'<p><a href="/user_uploads/{path_id}">image</a></p>'
            message_id = self.send_message_content(content)
            self.assert_message_content_is(message_id, expected)

        # Confirm no inline preview element snuck in via the
        # link-preview code path.
        msg = Message.objects.get(id=message_id)
        assert msg.rendered_content is not None
        self.assertNotIn("inline-image", msg.rendered_content)
        self.assertNotIn("message_inline_image", msg.rendered_content)
