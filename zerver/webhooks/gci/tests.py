from zerver.lib.test_classes import WebhookTestCase


class GoogleCodeInTests(WebhookTestCase):
    CHANNEL_NAME = "gci"
    URL_TEMPLATE = "/api/v1/external/gci?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "gci"

    def test_abandon_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**student-yqqtag** abandoned the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/)."
        self.check_webhook("task_abandoned_by_student", expected_topic_name, expected_message)

    def test_comment_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**student-yqqtag** commented on the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/)."
        self.check_webhook("student_commented_on_task", expected_topic_name, expected_message)

    def test_submit_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**student-yqqtag** submitted the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/)."
        self.check_webhook("task_submitted_by_student", expected_topic_name, expected_message)

    def test_claim_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**student-yqqtag** claimed the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/)."
        self.check_webhook("task_claimed_by_student", expected_topic_name, expected_message)

    def test_approve_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**eeshangarg** approved the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/)."
        self.check_webhook("task_approved_by_mentor", expected_topic_name, expected_message)

    def test_approve_pending_pc_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**eeshangarg** approved the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/) (pending parental consent)."
        self.check_webhook(
            "task_approved_by_mentor_pending_parental_consent",
            expected_topic_name,
            expected_message,
        )

    def test_needswork_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**eeshangarg** submitted the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/5136918324969472/) for more work."
        self.check_webhook(
            "task_submitted_by_mentor_for_more_work", expected_topic_name, expected_message
        )

    def test_extend_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**eeshangarg** extended the deadline for the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/) by 1.0 day(s)."
        self.check_webhook(
            "task_deadline_extended_by_mentor", expected_topic_name, expected_message
        )

    def test_unassign_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "**eeshangarg** unassigned **student-yqqtag** from the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/)."
        self.check_webhook("student_unassigned_by_mentor", expected_topic_name, expected_message)

    def test_outoftime_event_message(self) -> None:
        expected_topic_name = "student-yqqtag"
        expected_message = "The deadline for the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6694926301528064/) has passed."
        self.check_webhook("task_deadline_has_passed", expected_topic_name, expected_message)
