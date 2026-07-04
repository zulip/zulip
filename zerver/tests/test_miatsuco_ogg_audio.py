from zerver.lib.test_miatsuco import MiatsucoMarkdownTestMixin


class MiatsucoOggAudioPreviewTest(MiatsucoMarkdownTestMixin):
    def test_inline_ogg_audio_preview(self) -> None:
        # Ogg is an open standard container; we accept the tradeoff
        # that Safari lacks reliable native playback support for it
        # and don't special-case that browser.
        url, path_id = self.upload_file_and_get_path_id("filename.ogg", "audio/ogg")
        message_id = self.send_message_content(f"![Audio link](/user_uploads/{path_id})")
        expected = (
            f'<p><audio controls preload="metadata" src="{url}" title="Audio link"></audio></p>'
        )
        self.assert_message_content_is(message_id, expected)

    def test_inline_ogg_audio_preview_legacy_mimetype(self) -> None:
        # Some browsers report the legacy, pre-RFC-5334 generic Ogg
        # container type (application/ogg) for the File API's
        # file.type rather than audio/ogg; the server needs to treat
        # this the same as audio/ogg for uploaded files.
        url, path_id = self.upload_file_and_get_path_id("filename.ogg", "application/ogg")
        message_id = self.send_message_content(f"![Audio link](/user_uploads/{path_id})")
        expected = (
            f'<p><audio controls preload="metadata" src="{url}" title="Audio link"></audio></p>'
        )
        self.assert_message_content_is(message_id, expected)
