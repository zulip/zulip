from bs4 import BeautifulSoup
from unittest import TestCase

#from tools.lib.capitalization import check_capitalization, is_capitalized, get_safe_text

from zerver.lib.generateData import removeActions


class CheckRemoveActions(TestCase):
    def test_remove_leading_action(self):
        string = "[Walks to the dresser.] This looks interesting."
        result = removeActions(string)
        self.assertEqual(result, "This looks interesting.")

    def test_remove_trailingaction(self):
        string = "This looks interesting. [Walks to the dresser.]"
        result = removeActions(string)
        self.assertEqual(result, "This looks interesting.")

    def test_remove_middle_action(self):
        string = "This looks [Walks to the dresser.] interesting."
        result = removeActions(string)
        self.assertEqual(result, "This looks  interesting.")

