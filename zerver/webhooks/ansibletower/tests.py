# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class AnsibletowerHookTests(WebhookTestCase):
    STREAM_NAME = 'ansibletower'
    URL_TEMPLATE = "/api/v1/external/ansibletower?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'ansibletower'

    def test_ansibletower_project_update_successful_message(self) -> None:
        """
        Tests if ansibletower project update successful notification is handled correctly
        """
        expected_topic = "AWX - Project Update"
        expected_message = ("Project Update: [#2677 AWX - Project Update]"
                            "(http://awx.example.co.uk/#/jobs/project/2677) was successful")

        self.send_and_test_stream_message('project_update_successful', expected_topic, expected_message)

    def test_ansibletower_project_update_failed_message(self) -> None:
        """
        Tests if ansibletower project update failed notification is handled correctly
        """
        expected_topic = "AWX - Project Update"
        expected_message = ("Project Update: [#2678 AWX - Project Update]"
                            "(http://awx.example.co.uk/#/jobs/project/2678) failed")

        self.send_and_test_stream_message('project_update_failed', expected_topic, expected_message)

    def test_ansibletower_job_successful_multiple_hosts_message(self) -> None:
        """
        Tests if ansibletower job successful multiple hosts notification is handled correctly
        """
        expected_topic = "System - Deploy - Zabbix Agent"
        expected_message = ("Job: [#2674 System - Deploy - Zabbix Agent]"
                            "(http://awx.example.co.uk/#/jobs/playbook/2674) was successful\n"
                            "* chat.example.co.uk: Success\n"
                            "* devops.example.co.uk: Success\n"
                            "* gitlab.example.co.uk: Success\n"
                            "* ipa.example.co.uk: Success\n"
                            "* mail.example.co.uk: Success")

        self.send_and_test_stream_message('job_successful_multiple_hosts', expected_topic, expected_message)

    def test_ansibletower_job_successful_message(self) -> None:
        """
        Tests if ansibletower job successful notification is handled correctly
        """
        expected_topic = "System - Deploy - Zabbix Agent"
        expected_message = ("Job: [#2674 System - Deploy - Zabbix Agent]"
                            "(http://awx.example.co.uk/#/jobs/playbook/2674) was successful\n"
                            "* chat.example.co.uk: Success")

        self.send_and_test_stream_message('job_successful', expected_topic, expected_message)

    def test_ansibletower_job_failed_message(self) -> None:
        """
        Tests if ansibletower job failed notification is handled correctly
        """
        expected_topic = "System - Updates - Ubuntu"
        expected_message = ("Job: [#2722 System - Updates - Ubuntu]"
                            "(http://awx.example.co.uk/#/jobs/playbook/2722) failed\n"
                            "* chat.example.co.uk: Failed")

        self.send_and_test_stream_message('job_failed', expected_topic, expected_message)

    def test_ansibletower_job_failed_multiple_hosts_message(self) -> None:
        """
        Tests if ansibletower job failed notification is handled correctly
        """
        expected_topic = "System - Updates - Ubuntu"
        expected_message = ("Job: [#2722 System - Updates - Ubuntu]"
                            "(http://awx.example.co.uk/#/jobs/playbook/2722) failed\n"
                            "* chat.example.co.uk: Failed\n"
                            "* devops.example.co.uk: Failed\n"
                            "* gitlab.example.co.uk: Failed\n"
                            "* ipa.example.co.uk: Failed\n"
                            "* mail.example.co.uk: Failed")

        self.send_and_test_stream_message('job_failed_multiple_hosts', expected_topic, expected_message)

    def test_ansibletower_inventory_update_successful_message(self) -> None:
        """
        Tests if ansibletower inventory update successful notification is handled correctly
        """
        expected_topic = "AWX - Inventory Update"
        expected_message = ("Inventory Update: [#2724 AWX - Inventory Update]"
                            "(http://awx.example.co.uk/#/jobs/inventory/2724) was successful")

        self.send_and_test_stream_message('inventory_update_successful', expected_topic, expected_message)

    def test_ansibletower_inventory_update_failed_message(self) -> None:
        """
        Tests if ansibletower inventory update failed notification is handled correctly
        """
        expected_topic = "AWX - Inventory Update"
        expected_message = ("Inventory Update: [#2724 AWX - Inventory Update]"
                            "(http://awx.example.co.uk/#/jobs/inventory/2724) failed")

        self.send_and_test_stream_message('inventory_update_failed', expected_topic, expected_message)

    def test_ansibletower_adhoc_command_successful_message(self) -> None:
        """
        Tests if ansibletower adhoc command successful notification is handled correctly
        """
        expected_topic = "shell: uname -r"
        expected_message = ("AdHoc Command: [#2726 shell: uname -r]"
                            "(http://awx.example.co.uk/#/jobs/command/2726) was successful")

        self.send_and_test_stream_message('adhoc_command_successful', expected_topic, expected_message)

    def test_ansibletower_adhoc_command_failed_message(self) -> None:
        """
        Tests if ansibletower adhoc command failed notification is handled correctly
        """
        expected_topic = "shell: uname -r"
        expected_message = ("AdHoc Command: [#2726 shell: uname -r]"
                            "(http://awx.example.co.uk/#/jobs/command/2726) failed")

        self.send_and_test_stream_message('adhoc_command_failed', expected_topic, expected_message)

    def test_ansibletower_system_job_successful_message(self) -> None:
        """
        Tests if ansibletower system job successful notification is handled correctly
        """
        expected_topic = "Cleanup Job Details"
        expected_message = ("System Job: [#2721 Cleanup Job Details]"
                            "(http://awx.example.co.uk/#/jobs/system/2721) was successful")

        self.send_and_test_stream_message('system_job_successful', expected_topic, expected_message)

    def test_ansibletower_system_job_failed_message(self) -> None:
        """
        Tests if ansibletower system job failed notification is handled correctly
        """
        expected_topic = "Cleanup Job Details"
        expected_message = ("System Job: [#2721 Cleanup Job Details]"
                            "(http://awx.example.co.uk/#/jobs/system/2721) failed")

        self.send_and_test_stream_message('system_job_failed', expected_topic, expected_message)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("ansibletower", fixture_name, file_type="json")
