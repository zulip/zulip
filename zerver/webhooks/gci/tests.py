# -*- coding: utf-8 -*-
from typing import Optional, Text

from zerver.lib.test_classes import WebhookTestCase

class GoogleCodeInTests(WebhookTestCase):
    STREAM_NAME = 'gci'
    URL_TEMPLATE = "/api/v1/external/gci?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'gci'

    def test_abandon_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**student-yqqtag** abandoned the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/).'
        self.send_and_test_stream_message('task_abandoned_by_student',
                                          expected_subject, expected_message)

    def test_comment_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**student-yqqtag** commented on the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/).'
        self.send_and_test_stream_message('student_commented_on_task',
                                          expected_subject, expected_message)

    def test_submit_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**student-yqqtag** submitted the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/).'
        self.send_and_test_stream_message('task_submitted_by_student',
                                          expected_subject, expected_message)

    def test_claim_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**student-yqqtag** claimed the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/).'
        self.send_and_test_stream_message('task_claimed_by_student',
                                          expected_subject, expected_message)

    def test_approve_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**eeshangarg** approved the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/).'
        self.send_and_test_stream_message('task_approved_by_mentor',
                                          expected_subject, expected_message)

    def test_approve_pending_pc_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**eeshangarg** approved the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/) (pending parental consent).'
        self.send_and_test_stream_message('task_approved_by_mentor_pending_parental_consent',
                                          expected_subject, expected_message)

    def test_needswork_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**eeshangarg** submitted the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/5136918324969472/) for more work.'
        self.send_and_test_stream_message('task_submitted_by_mentor_for_more_work',
                                          expected_subject, expected_message)

    def test_extend_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**eeshangarg** extended the deadline for the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/) by 1.0 day(s).'
        self.send_and_test_stream_message('task_deadline_extended_by_mentor',
                                          expected_subject, expected_message)

    def test_unassign_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'**eeshangarg** unassigned **student-yqqtag** from the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6296903092273152/).'
        self.send_and_test_stream_message('student_unassigned_by_mentor',
                                          expected_subject, expected_message)

    def test_outoftime_event_message(self) -> None:
        expected_subject = u'student-yqqtag'
        expected_message = u'The deadline for the task [Sails unspread it stopped at kearney](https://codein.withgoogle.com/dashboard/task-instances/6694926301528064/) has passed.'
        self.send_and_test_stream_message('task_deadline_has_passed',
                                          expected_subject, expected_message)
