from django.core.mail.message import sanitize_address

from zerver.lib.send_email import FromAddress, build_email
from zerver.lib.test_classes import ZulipTestCase

OVERLY_LONG_NAME = "Z̷̧̙̯͙̠͇̰̲̞̙͆́͐̅̌͐̔͑̚u̷̼͎̹̻̻̣̞͈̙͛͑̽̉̾̀̅̌͜͠͞ļ̛̫̻̫̰̪̩̠̣̼̏̅́͌̊͞į̴̛̛̩̜̜͕̘̂̑̀̈p̡̛͈͖͓̟͍̿͒̍̽͐͆͂̀ͅ A̰͉̹̅̽̑̕͜͟͡c̷͚̙̘̦̞̫̭͗̋͋̾̑͆̒͟͞c̵̗̹̣̲͚̳̳̮͋̈́̾̉̂͝ͅo̠̣̻̭̰͐́͛̄̂̿̏͊u̴̱̜̯̭̞̠͋͛͐̍̄n̸̡̘̦͕͓̬͌̂̎͊͐̎͌̕ť̮͎̯͎̣̙̺͚̱̌̀́̔͢͝ S͇̯̯̙̳̝͆̊̀͒͛̕ę̛̘̬̺͎͎́̔̊̀͂̓̆̕͢ͅc̨͎̼̯̩̽͒̀̏̄̌̚u̷͉̗͕̼̮͎̬͓͋̃̀͂̈̂̈͊͛ř̶̡͔̺̱̹͓̺́̃̑̉͡͞ͅi̶̺̭͈̬̞̓̒̃͆̅̿̀̄́t͔̹̪͔̥̣̙̍̍̍̉̑̏͑́̌ͅŷ̧̗͈͚̥̗͚͊͑̀͢͜͡"


class TestBuildEmail(ZulipTestCase):
    def test_build_SES_compatible_From_field(self) -> None:
        hamlet = self.example_user("hamlet")
        from_name = FromAddress.security_email_from_name(language="en")
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=from_name,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(
            mail.extra_headers["From"], "{} <{}>".format(from_name, FromAddress.NOREPLY)
        )

    def test_build_SES_compatible_From_field_limit(self) -> None:
        hamlet = self.example_user("hamlet")
        limit_length_name = "a" * (320 - len(sanitize_address(FromAddress.NOREPLY, "utf-8")) - 3)
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=limit_length_name,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(
            mail.extra_headers["From"], "{} <{}>".format(limit_length_name, FromAddress.NOREPLY)
        )

    def test_build_SES_incompatible_From_field(self) -> None:
        hamlet = self.example_user("hamlet")
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=OVERLY_LONG_NAME,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], FromAddress.NOREPLY)

    def test_build_SES_incompatible_From_field_limit(self) -> None:
        hamlet = self.example_user("hamlet")
        limit_length_name = "a" * (321 - len(sanitize_address(FromAddress.NOREPLY, "utf-8")) - 3)
        mail = build_email(
            "zerver/emails/password_reset",
            to_emails=[hamlet],
            from_name=limit_length_name,
            from_address=FromAddress.NOREPLY,
            language="en",
        )
        self.assertEqual(mail.extra_headers["From"], FromAddress.NOREPLY)
