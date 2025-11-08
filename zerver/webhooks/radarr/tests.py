from zerver.lib.test_classes import WebhookTestCase


class RadarrHookTests(WebhookTestCase):
    CHANNEL_NAME = "radarr"
    URL_TEMPLATE = "/api/v1/external/radarr?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "radarr"

    def test_radarr_test(self) -> None:
        """
        Tests if radarr test payload is handled correctly
        """
        expected_topic_name = "Radarr - Test"
        expected_message = "Radarr webhook has been successfully configured."
        self.check_webhook("radarr_test", expected_topic_name, expected_message)

    def test_radarr_application_update(self) -> None:
        """
        Tests if radarr application update payload is handled correctly
        """
        expected_topic_name = "Radarr - Application update"
        expected_message = "Radarr was updated from 4.2.0.6370 to 4.2.0.6372."
        self.check_webhook("radarr_application_update", expected_topic_name, expected_message)

    def test_radarr_health_check_warning(self) -> None:
        """
        Tests if radarr health check warning payload is handled correctly
        """
        expected_topic_name = "Health warning"
        expected_message = "No download client is available."
        self.check_webhook("radarr_health_check_warning", expected_topic_name, expected_message)

    def test_radarr_health_check_error(self) -> None:
        """
        Tests if radarr health check error payload is handled correctly
        """
        expected_topic_name = "Health error"
        expected_message = "Movie Gotham City Sirens (tmdbid 416649) was removed from TMDb."
        self.check_webhook("radarr_health_check_error", expected_topic_name, expected_message)

    def test_radarr_movie_renamed(self) -> None:
        """
        Tests if radarr movie renamed payload is handled correctly
        """
        expected_topic_name = "Marley & Me"
        expected_message = "The movie Marley & Me has been renamed."
        self.check_webhook("radarr_movie_renamed", expected_topic_name, expected_message)

    def test_radarr_movie_imported(self) -> None:
        """
        Tests if radarr movie imported payload is handled correctly
        """
        expected_topic_name = "Batman v Superman: Dawn of Justice"
        expected_message = "The movie Batman v Superman: Dawn of Justice has been imported."
        self.check_webhook("radarr_movie_imported", expected_topic_name, expected_message)

    def test_radarr_movie_imported_upgrade(self) -> None:
        """
        Tests if radarr movie imported upgrade payload is handled correctly
        """
        expected_topic_name = "Greenland"
        expected_message = "The movie Greenland has been upgraded from WEBRip-720p to WEBRip-1080p."
        self.check_webhook("radarr_movie_imported_upgrade", expected_topic_name, expected_message)

    def test_radarr_movie_grabbed(self) -> None:
        """
        Tests if radarr movie grabbed payload is handled correctly
        """
        expected_topic_name = "Greenland"
        expected_message = "The movie Greenland has been grabbed."
        self.check_webhook("radarr_movie_grabbed", expected_topic_name, expected_message)

    def test_radarr_movie_deleted(self) -> None:
        """
        Tests if radarr movie deleted payload is handled correctly
        """
        expected_topic_name = "Batman v Superman: Dawn of Justice"
        expected_message = (
            "The movie Batman v Superman: Dawn of Justice was deleted; its files were also deleted."
        )
        self.check_webhook("radarr_movie_deleted", expected_topic_name, expected_message)

    def test_radarr_movie_file_deleted(self) -> None:
        """
        Tests if radarr movie file deleted payload is handled correctly
        """
        expected_topic_name = "Marley & Me"
        expected_message = "A file with quality Bluray-1080p for the movie Marley & Me was deleted, because it is missing from disk."
        self.check_webhook("radarr_movie_file_deleted", expected_topic_name, expected_message)

    def test_radarr_movie_added(self) -> None:
        """
        Tests if radarr movie added payload is handled correctly
        """
        expected_topic_name = "Batman v Superman: Dawn of Justice"
        expected_message = "The movie Batman v Superman: Dawn of Justice was added."
        self.check_webhook("radarr_movie_added", expected_topic_name, expected_message)
