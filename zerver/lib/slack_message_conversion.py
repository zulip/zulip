import re
from typing import Any, Dict, Tuple, List

# stubs
ZerverFieldsT = Dict[str, Any]
AddedUsersT = Dict[str, int]

# Slack link can be in the format <http://www.foo.com|www.foo.com> and <http://foo.com/>
LINK_REGEX = r"""
              (<)                                                     # match '>'
              (http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?
                  ([a-z0-9]+([\-\.]{1}[a-z0-9]+)*)(\.)                # subdomain
                  ([a-z]{3,63}(:[0-9]{1,5})?)(\/[^>]*)?               # domain name has chars in range {3,63}
              (\|)?(?:\|([^>]+))?                                     # char after pipe (for slack links)
              (>)
              """
SLACK_USERMENTION_REGEX = r"""
                           (<@)                  # Start with '<@'
                               ([a-zA-Z0-9]+)    # Here we have the Slack id
                           (\|)?                 # We not always have a Vertical line in mention
                               ([a-zA-Z0-9]+)?   # If Vertical line is present, this is short name
                           (>)                   # ends with '>'
                           """
# Slack doesn't have mid-word message-formatting like Zulip.
# Hence, ~stri~ke doesn't format the word in slack, but ~~stri~~ke
# formats the word in Zulip
SLACK_STRIKETHROUGH_REGEX = r"""
                             (^|[ -(]|[+-/]|\*|\_|[:-?]|\{|\[|\||\^)     # Start after specified characters
                             (\~)                                  # followed by an asterisk
                                 ([ -)+-}—]*)([ -}]+)              # any character except asterisk
                             (\~)                                  # followed by an asterisk
                             ($|[ -']|[+-/]|[:-?]|\*|\_|\}|\)|\]|\||\^)  # ends with specified characters
                             """
SLACK_ITALIC_REGEX = r"""
                      (^|[ -(]|[+-/]|[:-?]|\{|\[|\||\^|~)
                      (\_)
                          ([ -^`~—]*)([ -^`-~]+)                  # any character
                      (\_)
                      ($|[ -']|[+-/]|[:-?]|\}|\)|\]|\||\^|~)
                      """
SLACK_BOLD_REGEX = r"""
                    (^|[ -(]|[+-/]|[:-?]|\{|\[|\||\^|~)
                    (\*)
                        ([ -)+-~—]*)([ -)+-~]+)                   # any character
                    (\*)
                    ($|[ -']|[+-/]|[:-?]|\}|\)|\]|\||\^|~)
                    """

def get_user_full_name(user: ZerverFieldsT) -> str:
    if user['deleted'] is False:
        if user['real_name'] == '':
            return user['name']
        else:
            return user['real_name']
    else:
        return user['name']

# Markdown mapping
def convert_to_zulip_markdown(text: str, users: List[ZerverFieldsT],
                              added_users: AddedUsersT) -> Tuple[str, List[int], bool]:
    mentioned_users_id = []
    text = convert_markdown_syntax(text, SLACK_BOLD_REGEX, "**")
    text = convert_markdown_syntax(text, SLACK_STRIKETHROUGH_REGEX, "~~")
    text = convert_markdown_syntax(text, SLACK_ITALIC_REGEX, "*")

    # Map Slack's mention all: '<!everyone>' to '@**all** '
    # No regex for this as it can be present anywhere in the sentence
    text = text.replace('<!everyone>', '@**all**')

    tokens = text.split(' ')
    for iterator in range(len(tokens)):

        # Check user mentions and change mention format from
        # '<@slack_id|short_name>' to '@**full_name**'
        if (re.findall(SLACK_USERMENTION_REGEX, tokens[iterator], re.VERBOSE)):
            tokens[iterator], user_id = get_user_mentions(tokens[iterator],
                                                          users, added_users)
            if user_id is not None:
                mentioned_users_id.append(user_id)

    text = ' '.join(tokens)

    # Check and convert link format
    text, has_link = convert_link_format(text)

    return text, mentioned_users_id, has_link

def get_user_mentions(token: str, users: List[ZerverFieldsT],
                      added_users: AddedUsersT) -> Tuple[str, int]:
    slack_usermention_match = re.search(SLACK_USERMENTION_REGEX, token, re.VERBOSE)
    short_name = slack_usermention_match.group(4)
    slack_id = slack_usermention_match.group(2)
    for user in users:
        if (user['id'] == slack_id and user['name'] == short_name and short_name) or \
           (user['id'] == slack_id and short_name is None):
                full_name = get_user_full_name(user)
                user_id = added_users[slack_id]
                mention = "@**" + full_name + "**"
                token = re.sub(SLACK_USERMENTION_REGEX, mention, token, flags=re.VERBOSE)
                return token, user_id
    return token, None

# Map italic, bold and strikethrough markdown
def convert_markdown_syntax(text: str, regex: str, zulip_keyword: str) -> str:
    """
    Returns:
    1. For strikethrough formatting: This maps Slack's '~strike~' to Zulip's '~~strike~~'
    2. For bold formatting: This maps Slack's '*bold*' to Zulip's '**bold**'
    3. For italic formatting: This maps Slack's '_italic_' to Zulip's '*italic*'
    """
    for match in re.finditer(regex, text, re.VERBOSE):
        converted_token = (match.group(1) + zulip_keyword + match.group(3)
                           + match.group(4) + zulip_keyword + match.group(6))
        text = text.replace(match.group(0), converted_token)
    return text

def convert_link_format(text: str) -> Tuple[str, bool]:
    """
    1. Converts '<https://foo.com>' to 'https://foo.com'
    2. Converts '<https://foo.com|foo>' to 'https://foo.com|foo'
    """
    has_link = False
    for match in re.finditer(LINK_REGEX, text, re.VERBOSE):
        converted_text = match.group(0).replace('>', '').replace('<', '')
        has_link = True
        text = text.replace(match.group(0), converted_text)
    return text, has_link
