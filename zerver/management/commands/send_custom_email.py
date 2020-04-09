import hashlib
import shutil
from argparse import ArgumentParser
from typing import Any, Dict, List

from zerver.lib.management import CommandError, ZulipBaseCommand
from zerver.lib.send_email import FromAddress, send_email
from zerver.models import UserProfile
from zerver.templatetags.app_filters import render_markdown_path
from scripts.setup.inline_email_css import inline_template


def send_custom_email(users: List[UserProfile], options: Dict[str, Any]) -> None:
    """
    Can be used directly with from a management shell with
    send_custom_email(user_profile_list, dict(
        markdown_template_path="/path/to/markdown/file.md",
        subject="Email Subject",
        from_name="Sender Name")
    )
    """

    with open(options["markdown_template_path"]) as f:
        email_template_hash = hashlib.sha256(f.read().encode('utf-8')).hexdigest()[0:32]
    email_filename = "custom_email_%s.source.html" % (email_template_hash,)
    email_id = "zerver/emails/custom_email_%s" % (email_template_hash,)
    markdown_email_base_template_path = "templates/zerver/emails/custom_email_base.pre.html"
    html_source_template_path = "templates/%s.source.html" % (email_id,)
    plain_text_template_path = "templates/%s.txt" % (email_id,)
    subject_path = "templates/%s.subject.txt" % (email_id,)

    # First, we render the markdown input file just like our
    # user-facing docs with render_markdown_path.
    shutil.copyfile(options['markdown_template_path'], plain_text_template_path)

    rendered_input = render_markdown_path(plain_text_template_path.replace("templates/", ""))

    # And then extend it with our standard email headers.
    with open(html_source_template_path, "w") as f:
        with open(markdown_email_base_template_path) as base_template:
            # Note that we're doing a hacky non-Jinja2 substitution here;
            # we do this because the normal render_markdown_path ordering
            # doesn't commute properly with inline_email_css.
            f.write(base_template.read().replace('{{ rendered_input }}',
                                                 rendered_input))

    with open(subject_path, "w") as f:
        f.write(options["subject"])

    # Then, we compile the email template using inline_email_css to
    # add our standard styling to the paragraph tags (etc.).
    inline_template(email_filename)

    # Finally, we send the actual emails.
    for user_profile in users:
        context = {
            'realm_uri': user_profile.realm.uri,
            'realm_name': user_profile.realm.name,
        }
        send_email(email_id, to_user_ids=[user_profile.id],
                   from_address=FromAddress.SUPPORT,
                   reply_to_email=options.get("reply_to"),
                   from_name=options["from_name"], context=context)

class Command(ZulipBaseCommand):
    help = """Send email to specified email address."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--entire-server', action="store_true", default=False,
                            help="Send to every user on the server. ")
        parser.add_argument('--markdown-template-path', '--path',
                            dest='markdown_template_path',
                            required=True,
                            type=str,
                            help='Path to a markdown-format body for the email')
        parser.add_argument('--subject',
                            required=True,
                            type=str,
                            help='Subject line for the email')
        parser.add_argument('--from-name',
                            required=True,
                            type=str,
                            help='From line for the email')
        parser.add_argument('--reply-to',
                            type=str,
                            help='Optional reply-to line for the email')

        self.add_user_list_args(parser,
                                help="Email addresses of user(s) to send emails to.",
                                all_users_help="Send to every user on the realm.")
        self.add_realm_args(parser)

    def handle(self, *args: Any, **options: str) -> None:
        if options["entire_server"]:
            users = UserProfile.objects.filter(is_active=True, is_bot=False,
                                               is_mirror_dummy=False)
        else:
            realm = self.get_realm(options)
            try:
                users = self.get_users(options, realm, is_bot=False)
            except CommandError as error:
                if str(error) == "You have to pass either -u/--users or -a/--all-users.":
                    raise CommandError("You have to pass -u/--users or -a/--all-users or --entire-server.")
                raise error

        send_custom_email(users, options)
