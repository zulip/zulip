from typing import Text

emoji_list = {
    ":)": ":simple_smile:",
    ":-)": ":simple_smile:",
    ";)": ":wink:",
    ";-)": ":wink:",
    ":(": ":disappointed:",
    ":-(": ":disappointed:",
    ":'(": ":cry:",
    ":'-(": ":cry:",
    ":D": ":smiley:",
    ":-D": ":smiley:",
    "<3": ":heart:"
}

def convert_emoji(message: Text) -> Text:
    for i in emoji_list:
        message = message.replace(i, emoji_list[i])
    return message
