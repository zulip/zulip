from zerver.lib.test_classes import WebhookTestCase


class AnytypeWebhookTest(WebhookTestCase):
    CHANNEL_NAME = "anytype"
    URL_TEMPLATE = "/api/v1/external/anytype?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "anytype"

    def test_object_created_note(self) -> None:
        expected_topic_name = "Personal Notes"
        expected_message = """📝 New **note** created: **Meeting Notes - Q1 Planning**

> Quick notes from today's quarterly planning meeting. Discussed budget allocation and team goals.
*Space: Personal Notes by Alice Johnson*"""
        
        self.check_webhook("object_created_note", expected_topic_name, expected_message)

    def test_object_created_task(self) -> None:
        expected_topic_name = "Project Alpha"
        expected_message = """✅ New **task** created: **Review API Documentation**
*Space: Project Alpha by Bob Smith*"""
        
        self.check_webhook("object_created_task", expected_topic_name, expected_message)

    def test_object_updated_page(self) -> None:
        expected_topic_name = "Team Wiki"
        expected_message = """✏️ **page** updated: **Development Guidelines**
*Space: Team Wiki by Carol Davis*"""
        
        self.check_webhook("object_updated_page", expected_topic_name, expected_message)

    def test_object_deleted_note(self) -> None:
        expected_topic_name = "Personal Notes"
        expected_message = """🗑️ **note** deleted: **Old Draft Notes**
*Space: Personal Notes by Alice Johnson*"""
        
        self.check_webhook("object_deleted_note", expected_topic_name, expected_message)

    def test_object_archived_project(self) -> None:
        expected_topic_name = "Completed Projects"
        expected_message = """📦 **project** archived: **Website Redesign**
*Space: Completed Projects by David Wilson*"""
        
        self.check_webhook("object_archived_project", expected_topic_name, expected_message)

    def test_object_restored_task(self) -> None:
        expected_topic_name = "Active Tasks"
        expected_message = """♻️ **task** restored: **Fix Login Bug**
*Space: Active Tasks by Eve Martinez*"""
        
        self.check_webhook("object_restored_task", expected_topic_name, expected_message)

    def test_minimal_payload(self) -> None:
        """Test with minimal required fields only."""
        expected_topic_name = "Anytype"
        expected_message = "✏️ **object** updated: **Untitled**"
        
        self.check_webhook("minimal_payload", expected_topic_name, expected_message)

    def test_custom_topic(self) -> None:
        """Test with user-specified topic."""
        expected_topic_name = "Custom Topic"
        expected_message = """📄 New **page** created: **Project Proposal**
*by Frank Thompson*"""
        
        self.url = self.build_webhook_url(topic=expected_topic_name)
        self.check_webhook("object_created_page_custom_topic", expected_topic_name, expected_message)

    def test_unsupported_event_type(self) -> None:
        """Test handling of unsupported event types."""
        with self.assertRaises(Exception):
            self.check_webhook("unsupported_event", "topic", "message")