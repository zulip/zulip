from unittest.mock import MagicMock, patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.validator import to_wild_value
from zerver.webhooks.notion.view import (
    extract_datasource_title,
    extract_page_title,
    format_comment_message,
    format_message,
    get_author_name,
    get_datasource_title,
    get_notion_api_headers,
    get_page_title,
    get_user_name,
)


class NotionWebhookTest(WebhookTestCase):
    CHANNEL_NAME = "notion"
    URL_TEMPLATE = "/api/v1/external/notion?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "notion"

    def test_verification_request(self) -> None:
        expected_topic = "Notion Webhook Verification"
        expected_message = """
This is a webhook configuration test message from Notion.

Your verification token is: `secret_tMrlL1qK5vuQAh1b6cZGhFChZTSYJlce98V0pYn7yBl`

Please copy this token and paste it into your Notion webhook configuration to complete the setup.
""".strip()
        self.check_webhook(
            "verification", expected_topic, expected_message, content_type="application/json"
        )

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Project Plan")
    def test_page_created(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** created page **Project Plan**"
        self.check_webhook("page_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Meeting Notes")
    def test_page_content_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated page **Meeting Notes's** content"
        self.check_webhook("page_content_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Project Plan")
    def test_page_properties_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated page **Project Plan's** properties"
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Old Document")
    def test_page_moved(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** moved page **Old Document**"
        self.check_webhook("page_moved", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Archived Page")
    def test_page_deleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** moved page **Archived Page** to trash"
        self.check_webhook("page_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Restored Page")
    def test_page_undeleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** restored page **Restored Page** from trash"
        self.check_webhook("page_undeleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Confidential Doc")
    def test_page_locked(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** locked page **Confidential Doc**"
        self.check_webhook("page_locked", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Shared Doc")
    def test_page_unlocked(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** unlocked page **Shared Doc**"
        self.check_webhook("page_unlocked", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Task Tracker")
    def test_database_created(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** created database **Task Tracker**"
        self.check_webhook("database_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Project Board")
    def test_database_content_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated database **Project Board's** content"
        self.check_webhook("database_content_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Task Tracker")
    def test_database_moved(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** moved database **Task Tracker**"
        self.check_webhook("database_moved", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Old Database")
    def test_database_deleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** moved database **Old Database** to trash"
        self.check_webhook("database_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Restored DB")
    def test_database_undeleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** restored database **Restored DB** from trash"
        self.check_webhook("database_undeleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Task Tracker")
    def test_database_schema_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated database **Task Tracker's** schema"
        self.check_webhook("database_schema_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="API Data")
    def test_data_source_content_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated data source **API Data's** content"
        self.check_webhook("data_source_content_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="New Data Source")
    def test_data_source_created(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** created data source **New Data Source**"
        self.check_webhook("data_source_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Old Data Source")
    def test_data_source_deleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** moved data source **Old Data Source** to trash"
        self.check_webhook("data_source_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Moved Data")
    def test_data_source_moved(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** moved data source **Moved Data**"
        self.check_webhook("data_source_moved", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Schema Data")
    def test_data_source_schema_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated data source **Schema Data's** schema"
        self.check_webhook("data_source_schema_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Restored Data")
    def test_data_source_undeleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** restored data source **Restored Data** from trash"
        self.check_webhook("data_source_undeleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Discussion Page")
    def test_comment_created(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** added a comment on **Discussion Page**"
        self.check_webhook("comment_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Block Page")
    def test_comment_created_on_block(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** added a comment on a block in **Block Page**"
        self.check_webhook("comment_created_on_block", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Discussion Page")
    def test_comment_updated(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** updated a comment on **Discussion Page**"
        self.check_webhook("comment_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Discussion Page")
    def test_comment_deleted(self, mock_title: object, mock_user: object) -> None:
        expected_topic = "Notion"
        expected_message = "**Jane Doe** deleted a comment on a block in **Discussion Page**"
        self.check_webhook("comment_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Project Plan")
    def test_page_created_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Project Plan"
        expected_message = "**Jane Doe** created page **Project Plan**"
        self.check_webhook("page_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Meeting Notes")
    def test_page_content_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Meeting Notes"
        expected_message = "**Jane Doe** updated page **Meeting Notes's** content"
        self.check_webhook("page_content_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Project Plan")
    def test_page_properties_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Project Plan"
        expected_message = "**Jane Doe** updated page **Project Plan's** properties"
        self.check_webhook("page_properties_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Old Document")
    def test_page_moved_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Old Document"
        expected_message = "**Jane Doe** moved page **Old Document**"
        self.check_webhook("page_moved", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Archived Page")
    def test_page_deleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Archived Page"
        expected_message = "**Jane Doe** moved page **Archived Page** to trash"
        self.check_webhook("page_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Restored Page")
    def test_page_undeleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Restored Page"
        expected_message = "**Jane Doe** restored page **Restored Page** from trash"
        self.check_webhook("page_undeleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Confidential Doc")
    def test_page_locked_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Confidential Doc"
        expected_message = "**Jane Doe** locked page **Confidential Doc**"
        self.check_webhook("page_locked", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Shared Doc")
    def test_page_unlocked_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Shared Doc"
        expected_message = "**Jane Doe** unlocked page **Shared Doc**"
        self.check_webhook("page_unlocked", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Task Tracker")
    def test_database_created_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "db: Task Tracker"
        expected_message = "**Jane Doe** created database **Task Tracker**"
        self.check_webhook("database_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Project Board")
    def test_database_content_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "db: Project Board"
        expected_message = "**Jane Doe** updated database **Project Board's** content"
        self.check_webhook("database_content_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Task Tracker")
    def test_database_moved_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "db: Task Tracker"
        expected_message = "**Jane Doe** moved database **Task Tracker**"
        self.check_webhook("database_moved", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Old Database")
    def test_database_deleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "db: Old Database"
        expected_message = "**Jane Doe** moved database **Old Database** to trash"
        self.check_webhook("database_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Restored DB")
    def test_database_undeleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "db: Restored DB"
        expected_message = "**Jane Doe** restored database **Restored DB** from trash"
        self.check_webhook("database_undeleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Task Tracker")
    def test_database_schema_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "db: Task Tracker"
        expected_message = "**Jane Doe** updated database **Task Tracker's** schema"
        self.check_webhook("database_schema_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="API Data")
    def test_data_source_content_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "ds: API Data"
        expected_message = "**Jane Doe** updated data source **API Data's** content"
        self.check_webhook("data_source_content_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="New Data Source")
    def test_data_source_created_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "ds: New Data Source"
        expected_message = "**Jane Doe** created data source **New Data Source**"
        self.check_webhook("data_source_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Old Data Source")
    def test_data_source_deleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "ds: Old Data Source"
        expected_message = "**Jane Doe** moved data source **Old Data Source** to trash"
        self.check_webhook("data_source_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Moved Data")
    def test_data_source_moved_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "ds: Moved Data"
        expected_message = "**Jane Doe** moved data source **Moved Data**"
        self.check_webhook("data_source_moved", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Schema Data")
    def test_data_source_schema_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "ds: Schema Data"
        expected_message = "**Jane Doe** updated data source **Schema Data's** schema"
        self.check_webhook("data_source_schema_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_datasource_title", return_value="Restored Data")
    def test_data_source_undeleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "ds: Restored Data"
        expected_message = "**Jane Doe** restored data source **Restored Data** from trash"
        self.check_webhook("data_source_undeleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Discussion Page")
    def test_comment_created_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Discussion Page"
        expected_message = "**Jane Doe** added a comment on **Discussion Page**"
        self.check_webhook("comment_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Block Page")
    def test_comment_created_on_block_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Block Page"
        expected_message = "**Jane Doe** added a comment on a block in **Block Page**"
        self.check_webhook("comment_created_on_block", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Discussion Page")
    def test_comment_updated_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Discussion Page"
        expected_message = "**Jane Doe** updated a comment on **Discussion Page**"
        self.check_webhook("comment_updated", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Discussion Page")
    def test_comment_deleted_with_map_pages_to_topics(
        self, mock_title: object, mock_user: object
    ) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "page: Discussion Page"
        expected_message = "**Jane Doe** deleted a comment on a block in **Discussion Page**"
        self.check_webhook("comment_deleted", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Project Plan")
    def test_user_specified_topic(self, mock_title: object, mock_user: object) -> None:
        self.url = self.build_webhook_url(topic="Custom Topic", notion_token="test_token")
        expected_topic = "Custom Topic"
        expected_message = "**Jane Doe** created page **Project Plan**"
        self.check_webhook("page_created", expected_topic, expected_message)

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="")
    @patch("zerver.webhooks.notion.view.get_page_title", return_value="Unknown Page")
    def test_page_created_with_unknown_title(self, mock_title: object, mock_user: object) -> None:
        self.url = self.build_webhook_url(map_pages_to_topics="true", notion_token="test_token")
        expected_topic = "Notion Page"
        expected_message = "New page **Unknown Page** was created"
        self.check_webhook("page_created", expected_topic, expected_message)


class NotionHelperFunctionTest(WebhookTestCase):
    CHANNEL_NAME = "notion"
    URL_TEMPLATE = "/api/v1/external/notion?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "notion"

    def test_extract_page_title_with_valid_data(self) -> None:
        page_data = {
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"plain_text": "My Test Page"}],
                }
            }
        }
        result = extract_page_title(page_data)
        self.assertEqual(result, "My Test Page")

    def test_extract_page_title_with_name_property(self) -> None:
        page_data = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Named Page"}],
                }
            }
        }
        result = extract_page_title(page_data)
        self.assertEqual(result, "Named Page")

    def test_extract_page_title_with_fallback_iteration(self) -> None:
        page_data = {
            "properties": {
                "custom_title_field": {
                    "type": "title",
                    "title": [{"plain_text": "Custom Title"}],
                }
            }
        }
        result = extract_page_title(page_data)
        self.assertEqual(result, "Custom Title")

    def test_extract_page_title_with_empty_data(self) -> None:
        result = extract_page_title({})
        self.assertEqual(result, "Untitled Page")

        result = extract_page_title({"properties": {}})
        self.assertEqual(result, "Untitled Page")

    def test_extract_datasource_title_with_valid_data(self) -> None:
        db_data = {"title": [{"plain_text": "My Database"}]}
        result = extract_datasource_title(db_data)
        self.assertEqual(result, "My Database")

    def test_extract_datasource_title_with_empty_data(self) -> None:
        result = extract_datasource_title({})
        self.assertEqual(result, "Untitled Data Source")

        result = extract_datasource_title({"title": []})
        self.assertEqual(result, "Untitled Data Source")

    def test_get_notion_api_headers(self) -> None:
        headers = get_notion_api_headers("test_token")
        self.assertEqual(headers["Authorization"], "Bearer test_token")
        self.assertEqual(headers["Notion-Version"], "2025-09-03")
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_get_page_title_without_token(self) -> None:
        result = get_page_title("", "page_id")
        self.assertEqual(result, "Unknown Page")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_page_title_with_api_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {"title": {"type": "title", "title": [{"plain_text": "API Page"}]}}
        }
        mock_get.return_value = mock_response

        result = get_page_title("token", "page_id")
        self.assertEqual(result, "API Page")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_page_title_with_api_failure(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_page_title("token", "page_id")
        self.assertEqual(result, "Unknown Page")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_page_title_with_exception(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("Network error")

        result = get_page_title("token", "page_id")
        self.assertEqual(result, "Unknown Page")

    def test_get_datasource_title_without_token(self) -> None:
        result = get_datasource_title("", "db_id")
        self.assertEqual(result, "Unknown Data Source")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_datasource_title_with_api_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": [{"plain_text": "API Database"}]}
        mock_get.return_value = mock_response

        result = get_datasource_title("token", "db_id")
        self.assertEqual(result, "API Database")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_datasource_title_with_api_failure(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_datasource_title("token", "db_id")
        self.assertEqual(result, "Unknown Data Source")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_datasource_title_with_exception(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("Connection error")

        result = get_datasource_title("token", "db_id")
        self.assertEqual(result, "Unknown Data Source")

    def test_get_user_name_without_token(self) -> None:
        result = get_user_name("", "user_id")
        self.assertEqual(result, "Unknown user")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_api_success(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "John Doe"}
        mock_get.return_value = mock_response

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "John Doe")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_email_fallback(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "type": "person",
            "person": {"email": "john.doe@example.com"},
        }
        mock_get.return_value = mock_response

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "John Doe")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_fallback(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"type": "bot"}
        mock_get.return_value = mock_response

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "Unknown user")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_api_failure(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "Unknown user")

    @patch("zerver.webhooks.notion.view.requests.get")
    def test_get_user_name_with_exception(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("API error")

        result = get_user_name("token", "user_id")
        self.assertEqual(result, "Unknown user")

    def test_format_message_without_author(self) -> None:
        template = (
            "**{author}** updated {entity_type} **{entity}{suffix}**{content}",
            "{entity_type} **{entity}{suffix}** was updated{content}",
        )
        result = format_message(template, "", "Test Page", "page", "'s content", "")
        self.assertEqual(result, "page **Test Page's content** was updated")

    def test_format_comment_message_without_author(self) -> None:
        template = (
            "**{author}** added a comment on {target}",
            "A comment was added on {target}",
        )
        result = format_comment_message(template, "", "**Test Page**")
        self.assertEqual(result, "A comment was added on **Test Page**")

    def test_get_author_name_no_authors(self) -> None:
        payload = to_wild_value("payload", '{"type": "page.created"}')
        result = get_author_name(payload, "token")
        self.assertEqual(result, "")

    def test_get_author_name_empty_authors_list(self) -> None:
        payload = to_wild_value("payload", '{"type": "page.created", "authors": []}')
        result = get_author_name(payload, "token")
        self.assertEqual(result, "")

    def test_get_author_name_invalid_user_id(self) -> None:
        payload = to_wild_value(
            "payload", '{"type": "page.created", "authors": [{"id": "", "type": "user"}]}'
        )
        result = get_author_name(payload, "token")
        self.assertEqual(result, "")

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    def test_get_author_name_multiple_authors(self, mock_user: object) -> None:
        payload = to_wild_value(
            "payload",
            '{"type": "page.created", "authors": [{"id": "user1", "type": "user"}, {"id": "user2", "type": "user"}]}',
        )
        result = get_author_name(payload, "token")
        self.assertEqual(result, "Jane Doe (+1 other)")

    @patch("zerver.webhooks.notion.view.get_user_name", return_value="Jane Doe")
    def test_get_author_name_many_authors(self, mock_user: object) -> None:
        payload = to_wild_value(
            "payload",
            '{"type": "page.created", "authors": [{"id": "user1", "type": "user"}, {"id": "user2", "type": "user"}, {"id": "user3", "type": "user"}]}',
        )
        result = get_author_name(payload, "token")
        self.assertEqual(result, "Jane Doe (+2 others)")

    def test_get_entity_event_message_empty_entity_id(self) -> None:
        from zerver.webhooks.notion.view import ENTITY_CREATED_TEMPLATE, get_entity_event_message

        payload = to_wild_value(
            "payload",
            '{"type": "page.created", "entity": {"id": "", "type": "page"}}',
        )
        topic, message = get_entity_event_message(
            payload,
            "",
            "page",
            "page",
            ENTITY_CREATED_TEMPLATE,
            lambda token, id: "Unknown Page",
            fallback_topic="Notion Page",
            fallback_message="New page was created",
        )
        self.assertEqual(topic, "Notion Page")
        self.assertEqual(message, "New page was created")
