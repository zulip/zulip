from zerver.lib.test_classes import WebhookTestCase


class SonarrHookTests(WebhookTestCase):
    CHANNEL_NAME = "sonarr"
    URL_TEMPLATE = "/api/v1/external/sonarr?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "sonarr"

    def test_sonarr_test(self) -> None:
        """
        Tests if sonarr test payload is handled correctly
        """
        expected_topic_name = "Sonarr - Test"
        expected_message = "Sonarr webhook has been successfully configured."
        self.check_webhook("sonarr_test", expected_topic_name, expected_message)

    def test_sonarr_series_deleted(self) -> None:
        """
        Tests if sonarr series deleted payload is handled correctly
        """
        expected_topic_name = "Breaking Bad"
        expected_message = "Breaking Bad has been deleted."
        self.check_webhook("sonarr_series_deleted", expected_topic_name, expected_message)

    def test_sonarr_health_check_warning(self) -> None:
        """
        Tests if sonarr health check warning payload is handled correctly
        """
        expected_topic_name = "Health warning"
        expected_message = "Indexers unavailable due to failures for more than 6 hours: Academic Torrents - Jackett, ACG - Jackett, KickAssTorrent - Jackett, EXT Torrents - Jackett, Extra Torrents - Jackett, SkyTorrents - Jackett, iDope - Jackett."
        self.check_webhook("sonarr_health_check_warning", expected_topic_name, expected_message)

    def test_sonarr_health_check_error(self) -> None:
        """
        Tests if sonarr health check error payload is handled correctly
        """
        expected_topic_name = "Health error"
        expected_message = "No indexers available with RSS sync enabled, Sonarr will not grab new releases automatically."
        self.check_webhook("sonarr_health_check_error", expected_topic_name, expected_message)

    def test_sonarr_episodes_renamed(self) -> None:
        """
        Tests if sonarr episodes renamed payload is handled correctly
        """
        expected_topic_name = "The L Word"
        expected_message = "The L Word episodes have been renamed."
        self.check_webhook("sonarr_episodes_renamed", expected_topic_name, expected_message)

    def test_sonarr_episode_imported(self) -> None:
        """
        Tests if sonarr episode imported payload is handled correctly
        """
        expected_topic_name = "Grey's Anatomy"
        expected_message = "Grey's Anatomy - 17x9 - In My Life has been imported."
        self.check_webhook("sonarr_episode_imported", expected_topic_name, expected_message)

    def test_sonarr_episode_imported_upgrade(self) -> None:
        """
        Tests if sonarr episode imported upgrade payload is handled correctly
        """
        expected_topic_name = "NCIS"
        expected_message = "NCIS - 18x10 - Watchdog has been upgraded from SDTV to HDTV-720p."
        self.check_webhook("sonarr_episode_imported_upgrade", expected_topic_name, expected_message)

    def test_sonarr_episode_grabbed(self) -> None:
        """
        Tests if sonarr episode grabbed payload is handled correctly
        """
        expected_topic_name = "NCIS"
        expected_message = "NCIS - 18x10 - Watchdog has been grabbed."
        self.check_webhook("sonarr_episode_grabbed", expected_topic_name, expected_message)

    def test_sonarr_episode_deleted(self) -> None:
        """
        Tests if sonarr episode deleted payload is handled correctly
        """
        expected_topic_name = "Breaking Bad"
        expected_message = "Breaking Bad - 1x1 - Pilot has been deleted."
        self.check_webhook("sonarr_episode_deleted", expected_topic_name, expected_message)

    def test_sonarr_episode_deleted_upgrade(self) -> None:
        """
        Tests if sonarr episode deleted upgrade payload is handled correctly
        """
        expected_topic_name = "S.W.A.T. (2017)"
        expected_message = (
            "S.W.A.T. (2017) - 4x10 - Buried has been deleted due to quality upgrade."
        )
        self.check_webhook("sonarr_episode_deleted_upgrade", expected_topic_name, expected_message)
