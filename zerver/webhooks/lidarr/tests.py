from zerver.lib.test_classes import WebhookTestCase


class LidarrHookTests(WebhookTestCase):
    CHANNEL_NAME = "lidarr"
    URL_TEMPLATE = "/api/v1/external/lidarr?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "lidarr"

    def test_lidarr_test(self) -> None:
        """
        Tests if lidarr test payload is handled correctly
        """
        expected_topic_name = "Lidarr - Test"
        expected_message = "Lidarr webhook has been successfully configured."
        self.check_webhook("lidarr_test", expected_topic_name, expected_message)

    def test_lidarr_tracks_renamed(self) -> None:
        """
        Tests if lidarr tracks renamed payload is handled correctly
        """
        expected_topic_name = "Little Mix"
        expected_message = "The artist Little Mix has had its tracks renamed."
        self.check_webhook("lidarr_tracks_renamed", expected_topic_name, expected_message)

    def test_lidarr_tracks_retagged(self) -> None:
        """
        Tests if lidarr tracks retagged payload is handled correctly
        """
        expected_topic_name = "Little Mix"
        expected_message = "The artist Little Mix has had its tracks retagged."
        self.check_webhook("lidarr_tracks_retagged", expected_topic_name, expected_message)

    def test_lidarr_tracks_imported(self) -> None:
        """
        Tests if lidarr tracks imported payload is handled correctly
        """
        expected_topic_name = "UB40"
        expected_message = """
The following tracks by UB40 have been imported:
* Cherry Oh Baby
* Keep On Moving
* Please Don't Make Me Cry
* Sweet Sensation
* Johnny Too Bad
* Red Red Wine
* Guilty
* She Caught the Train
* Version Girl
* Many Rivers to Cross
""".strip()
        self.check_webhook("lidarr_tracks_imported", expected_topic_name, expected_message)

    def test_lidarr_tracks_imported_upgrade(self) -> None:
        """
        Tests if lidarr tracks imported upgrade payload is handled correctly
        """
        expected_topic_name = "Little Mix"
        expected_message = """
The following tracks by Little Mix have been imported due to upgrade:
* The National Manthem
* Woman Like Me
* Think About Us
* Strip
* Monster in Me
* Joan of Arc
* Love a Girl Right
* American Boy
* Told You So
* Wasabi
* More Than Words
* Motivate
* Notice
* The Cure
* Forget You Not
* Woman’s World
* The Cure (stripped)
* Only You
""".strip()
        self.check_webhook("lidarr_tracks_imported_upgrade", expected_topic_name, expected_message)

    def test_lidarr_album_grabbed(self) -> None:
        """
        Tests if lidarr album grabbed payload is handled correctly
        """
        expected_topic_name = "UB40"
        expected_message = "The album Labour of Love by UB40 has been grabbed."
        self.check_webhook("lidarr_album_grabbed", expected_topic_name, expected_message)

    def test_lidarr_tracks_imported_over_limit(self) -> None:
        """
        Tests if lidarr tracks imported over limit payload is handled correctly
        """
        expected_topic_name = "Michael Jackson"
        expected_message = """
The following tracks by Michael Jackson have been imported:
* Scream
* Billie Jean
* The Way You Make Me Feel
* They Don’t Care About Us
* Stranger in Moscow
* Black or White
* This Time Around
* Rock With You
* Earth Song
* She’s Out of My Life
* D.S.
* Bad
* Money
* I Just Can’t Stop Loving You
* Man in the Mirror
* Come Together
* Thriller
* You Are Not Alone
* Beat It
* Childhood (theme from “Free Willy 2”)
[and 10 more tracks(s)]
""".strip()
        self.check_webhook(
            "lidarr_tracks_imported_over_limit", expected_topic_name, expected_message
        )

    def test_lidarr_tracks_imported_upgrade_over_limit(self) -> None:
        """
        Tests if lidarr tracks imported upgrade over limit payload is handled correctly
        """
        expected_topic_name = "Michael Jackson"
        expected_message = """
The following tracks by Michael Jackson have been imported due to upgrade:
* Scream
* Billie Jean
* The Way You Make Me Feel
* They Don’t Care About Us
* Stranger in Moscow
* Black or White
* This Time Around
* Rock With You
* Earth Song
* She’s Out of My Life
* D.S.
* Bad
* Money
* I Just Can’t Stop Loving You
* Man in the Mirror
* Come Together
* Thriller
* You Are Not Alone
* Beat It
* Childhood (theme from “Free Willy 2”)
[and 10 more tracks(s)]
""".strip()
        self.check_webhook(
            "lidarr_tracks_imported_upgrade_over_limit", expected_topic_name, expected_message
        )
