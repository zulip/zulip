from zerver.lib.test_classes import WebhookTestCase


class AnsibletowerHookTests(WebhookTestCase):
    CHANNEL_NAME = "ansibletower"
    URL_TEMPLATE = "/api/v1/external/ansibletower?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "ansibletower"

    def test_ansibletower_project_update_successful_message(self) -> None:
        """
        Tests if ansibletower project update successful notification is handled correctly
        """
        expected_topic_name = "AWX - Project Update"
        expected_message = (
            "Project Update: [#2677 AWX - Project Update]"
            "(http://awx.example.co.uk/#/jobs/project/2677) was successful."
        )

        self.check_webhook("project_update_successful", expected_topic_name, expected_message)

    def test_ansibletower_project_update_failed_message(self) -> None:
        """
        Tests if ansibletower project update failed notification is handled correctly
        """
        expected_topic_name = "AWX - Project Update"
        expected_message = (
            "Project Update: [#2678 AWX - Project Update]"
            "(http://awx.example.co.uk/#/jobs/project/2678) failed."
        )

        self.check_webhook("project_update_failed", expected_topic_name, expected_message)

    def test_ansibletower_job_successful_multiple_hosts_message(self) -> None:
        """
        Tests if ansibletower job successful multiple hosts notification is handled correctly
        """
        expected_topic_name = "System - Deploy - Zabbix Agent"
        expected_message = """
Job: [#2674 System - Deploy - Zabbix Agent](http://awx.example.co.uk/#/jobs/playbook/2674) was successful:
* chat.example.co.uk: Success
* devops.example.co.uk: Success
* gitlab.example.co.uk: Success
* ipa.example.co.uk: Success
* mail.example.co.uk: Success
""".strip()

        self.check_webhook("job_successful_multiple_hosts", expected_topic_name, expected_message)

    def test_ansibletower_job_successful_message(self) -> None:
        """
        Tests if ansibletower job successful notification is handled correctly
        """
        expected_topic_name = "System - Deploy - Zabbix Agent"
        expected_message = """
Job: [#2674 System - Deploy - Zabbix Agent](http://awx.example.co.uk/#/jobs/playbook/2674) was successful:
* chat.example.co.uk: Success
""".strip()

        self.check_webhook("job_successful", expected_topic_name, expected_message)

    def test_ansibletower_nine_job_successful_message(self) -> None:
        """
        Test to see if awx/ansibletower 9.x.x job successful notifications are
        handled just as successfully as prior to 9.x.x.
        """
        expected_topic_name = "Demo Job Template"
        expected_message = """
Job: [#1 Demo Job Template](https://towerhost/#/jobs/playbook/1) was successful:
* localhost: Success
""".strip()

        self.check_webhook(
            "job_complete_successful_awx_9.1.1", expected_topic_name, expected_message
        )

    def test_ansibletower_job_failed_message(self) -> None:
        """
        Tests if ansibletower job failed notification is handled correctly
        """
        expected_topic_name = "System - Updates - Ubuntu"
        expected_message = """
Job: [#2722 System - Updates - Ubuntu](http://awx.example.co.uk/#/jobs/playbook/2722) failed:
* chat.example.co.uk: Failed
""".strip()

        self.check_webhook("job_failed", expected_topic_name, expected_message)

    def test_ansibletower_job_failed_multiple_hosts_message(self) -> None:
        """
        Tests if ansibletower job failed notification is handled correctly
        """
        expected_topic_name = "System - Updates - Ubuntu"
        expected_message = """
Job: [#2722 System - Updates - Ubuntu](http://awx.example.co.uk/#/jobs/playbook/2722) failed:
* chat.example.co.uk: Failed
* devops.example.co.uk: Failed
* gitlab.example.co.uk: Failed
* ipa.example.co.uk: Failed
* mail.example.co.uk: Failed
""".strip()

        self.check_webhook("job_failed_multiple_hosts", expected_topic_name, expected_message)

    def test_ansibletower_inventory_update_successful_message(self) -> None:
        """
        Tests if ansibletower inventory update successful notification is handled correctly
        """
        expected_topic_name = "AWX - Inventory Update"
        expected_message = (
            "Inventory Update: [#2724 AWX - Inventory Update]"
            "(http://awx.example.co.uk/#/jobs/inventory/2724) was successful."
        )

        self.check_webhook("inventory_update_successful", expected_topic_name, expected_message)

    def test_ansibletower_inventory_update_failed_message(self) -> None:
        """
        Tests if ansibletower inventory update failed notification is handled correctly
        """
        expected_topic_name = "AWX - Inventory Update"
        expected_message = (
            "Inventory Update: [#2724 AWX - Inventory Update]"
            "(http://awx.example.co.uk/#/jobs/inventory/2724) failed."
        )

        self.check_webhook("inventory_update_failed", expected_topic_name, expected_message)

    def test_ansibletower_adhoc_command_successful_message(self) -> None:
        """
        Tests if ansibletower adhoc command successful notification is handled correctly
        """
        expected_topic_name = "shell: uname -r"
        expected_message = (
            "AdHoc Command: [#2726 shell: uname -r]"
            "(http://awx.example.co.uk/#/jobs/command/2726) was successful."
        )

        self.check_webhook("adhoc_command_successful", expected_topic_name, expected_message)

    def test_ansibletower_adhoc_command_failed_message(self) -> None:
        """
        Tests if ansibletower adhoc command failed notification is handled correctly
        """
        expected_topic_name = "shell: uname -r"
        expected_message = (
            "AdHoc Command: [#2726 shell: uname -r]"
            "(http://awx.example.co.uk/#/jobs/command/2726) failed."
        )

        self.check_webhook("adhoc_command_failed", expected_topic_name, expected_message)

    def test_ansibletower_system_job_successful_message(self) -> None:
        """
        Tests if ansibletower system job successful notification is handled correctly
        """
        expected_topic_name = "Cleanup Job Details"
        expected_message = (
            "System Job: [#2721 Cleanup Job Details]"
            "(http://awx.example.co.uk/#/jobs/system/2721) was successful."
        )

        self.check_webhook("system_job_successful", expected_topic_name, expected_message)

    def test_ansibletower_system_job_failed_message(self) -> None:
        """
        Tests if ansibletower system job failed notification is handled correctly
        """
        expected_topic_name = "Cleanup Job Details"
        expected_message = (
            "System Job: [#2721 Cleanup Job Details]"
            "(http://awx.example.co.uk/#/jobs/system/2721) failed."
        )

        self.check_webhook("system_job_failed", expected_topic_name, expected_message)
