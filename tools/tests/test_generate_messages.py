from unittest import TestCase

from zerver.lib.generate_test_data import remove_actions

class CheckRemoveActions(TestCase):
    def test_remove_leading_action(self):
        # type: () -> None
        string = "[Walks to the dresser.] This looks interesting."
        result = remove_actions(string)
        self.assertEqual(result, " This looks interesting.")

    def test_remove_trailingaction(self):
        # type: () -> None
        string = "This looks interesting. [Walks to the dresser.]"
        result = remove_actions(string)
        self.assertEqual(result, "This looks interesting. ")

    def test_remove_middle_action(self):
        # type: () -> None
        string = "This looks [Walks to the dresser.] interesting."
        result = remove_actions(string)
        self.assertEqual(result, "This looks  interesting.")
