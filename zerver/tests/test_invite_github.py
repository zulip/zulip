from zerver.lib.test_classes import ZulipTestCase

from zerver.views.invite import get_invitee_emails_set

class GithubInviteTest(ZulipTestCase):
    def test_github_invite_empty(self) -> None:
        # Empty test case 
        empty_string = ""
        empty_set = set()
        empty_set.add('')
        return_set = get_invitee_emails_set(empty_string)
        self.assertEqual(empty_set,return_set)
    def test_github_invite_with_email(self) -> None:
        # github mixed with emails
        goal_set = set()
        goal_set.add("foo@bar.com")
        goal_set.add("zulip-devel@googlegroups.com")
        input_string = "foo@bar.com,git<zulip>"
        output_set = get_invitee_emails_set(input_string)
        self.assertEqual(goal_set,output_set)
    def test_github_invite_invalid_entry(self) -> None:
        # invalid input
        goal_set = set()
        input_string = "git<invaliduserentry_raiseHTTPError>"
        output_set = get_invitee_emails_set(input_string)
        self.assertEqual(goal_set,output_set)
    def test_github_invite_stress(self) -> None:
        # Stress test
        input_string = ""
        for i in range(25):
            input_string += "zulip-devel@googlegroups.com,"
        input_string += "git<zulip>"
        output_set = get_invitee_emails_set(input_string)
        #print(len(output_set))
        for email in output_set:
            self.assertEqual(email,"zulip-devel@googlegroups.com")