// @ts-ignore
import _ from "lodash";

// @ts-ignore
import * as people from "./people";

// For simplicity, we use a list for our internal
// data, since that matches what the server sends us.

interface AlertWord {
    word: string;
}

interface Message {
    alerted: boolean;
    content: string;
}

let my_alert_words:string[] = [];


export function set_words(words: string[]):void {
    my_alert_words = words;
}

export function get_word_list():AlertWord[]{
    // Returns a array of objects
    // (with each alert_word as value and 'word' as key to the object.)
    const words:AlertWord[] = [];
    for (const word of my_alert_words) {
        words.push({word});
    }
    return words;
}

export function has_alert_word(word: string):boolean {
    return my_alert_words.includes(word);
}

const alert_regex_replacements:Map<string, string> = new Map([
    ["&", "&amp;"],
    ["<", "&lt;"],
    [">", "&gt;"],
    // Accept quotes with or without HTML escaping
    ['"', '(?:"|&quot;)'],
    ["'", "(?:'|&#39;)"],
]);

export function process_message(message: Message):void {
    // Parsing for alert words is expensive, so we rely on the host
    // to tell us there any alert words to even look for.
    if (!message.alerted) {
        return;
    }

    for (const word of my_alert_words) {
        const clean:string = _.escapeRegExp(word).replace(/["&'<>]/g, (c: string) =>
            alert_regex_replacements.get(c)!,
        );
        const before_punctuation:string = "\\s|^|>|[\\(\\\".,';\\[]";
        const after_punctuation:string = "(?=\\s)|$|<|[\\)\\\"\\?!:.,';\\]!]";

        const regex:RegExp = new RegExp(`(${before_punctuation})(${clean})(${after_punctuation})`, "ig");
        message.content = message.content.replace(
            regex,
            (match:string, before:string, word:string, after:string, offset:number, content:string) :string => {
                // Logic for ensuring that we don't muck up rendered HTML.
                const pre_match:string = content.slice(0, offset);
                // We want to find the position of the `<` and `>` only in the
                // match and the string before it. So, don't include the last
                // character of match in `check_string`. This covers the corner
                // case when there is an alert word just before `<` or `>`.
                const check_string:string = pre_match + match.slice(0, -1);
                const in_tag:boolean = check_string.lastIndexOf("<") > check_string.lastIndexOf(">");
                // Matched word is inside a HTML tag so don't perform any highlighting.
                if (in_tag) {
                    return before + word + after;
                }
                return before + "<span class='alert-word'>" + word + "</span>" + after;
            },
        );
    }
}
interface Messages {
    sender_email: string;
    alerted: boolean;
}

export function notifies(message: Messages) {
    // We exclude ourselves from notifications when we type one of our own
    // alert words into a message, just because that can be annoying for
    // certain types of workflows where everybody on your team, including
    // yourself, sets up an alert word to effectively mention the team.
    return !people.is_current_user(message.sender_email) && message.alerted;
}

type AlertWords = {
    alert_words: string[];
}

export const initialize = (params:AlertWords) :void => {
    my_alert_words = params.alert_words;
};
