import _ from "lodash";

import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import type {StateData} from "./state_data.ts";

// For simplicity, we use a list for our internal
// data, since that matches what the server sends us.
let my_alert_words: string[] = [];

export function set_words(words: string[]): void {
    // This module's highlighting algorithm of greedily created
    // highlight spans cannot correctly handle overlapping alert word
    // clauses, but processing in order from longest-to-shortest
    // reduces some symptoms of this. See #28415 for details.
    my_alert_words = words;
    my_alert_words.sort((a, b) => b.length - a.length);
}

export function get_word_list(): {word: string}[] {
    // Returns a array of objects
    // (with each alert_word as value and 'word' as key to the object.)
    const words = [];
    for (const word of my_alert_words) {
        words.push({word});
    }
    return words;
}

export function has_alert_word(word: string): boolean {
    return my_alert_words.includes(word);
}

const alert_regex_replacements = new Map<string, string>([
    ["&", "&amp;"],
    ["<", "&lt;"],
    [">", "&gt;"],
    // Accept quotes with or without HTML escaping
    ['"', '(?:"|&quot;)'],
    ["'", "(?:'|&#39;)"],
]);

export function process_message(message: Message): void {
    // Parsing for alert words is expensive, so we rely on the host
    // to tell us there any alert words to even look for.
    if (!message.alerted) {
        return;
    }

    for (const word of my_alert_words) {
        const clean = _.escapeRegExp(word).replaceAll(
            /["&'<>]/g,
            (c) => alert_regex_replacements.get(c)!,
        );
        const before_punctuation = "\\s|^|>|[\\(\\\".,';\\[]";
        const after_punctuation = "(?=\\s)|$|<|[\\)\\\"\\?!:.,';\\]!]";

        const regex = new RegExp(`(${before_punctuation})(${clean})(${after_punctuation})`, "ig");
        message.content = message.content.replace(
            regex,
            (
                match: string,
                before: string,
                word: string,
                after: string,
                offset: number,
                content: string,
            ) => {
                // Logic for ensuring that we don't muck up rendered HTML.
                const pre_match = content.slice(0, offset);
                // We want to find the position of the `<` and `>` only in the
                // match and the string before it. So, don't include the last
                // character of match in `check_string`. This covers the corner
                // case when there is an alert word just before `<` or `>`.
                const check_string = pre_match + match.slice(0, -1);
                const in_tag = check_string.lastIndexOf("<") > check_string.lastIndexOf(">");
                // Matched word is inside an HTML tag so don't perform any highlighting.
                if (in_tag) {
                    return before + word + after;
                }
                return before + "<span class='alert-word'>" + word + "</span>" + after;
            },
        );
    }
}

export function notifies(message: Message): boolean {
    // We exclude ourselves from notifications when we type one of our own
    // alert words into a message, just because that can be annoying for
    // certain types of workflows where everybody on your team, including
    // yourself, sets up an alert word to effectively mention the team.
    return !people.is_my_user_id(message.sender_id) && message.alerted;
}

export const initialize = (params: StateData["alert_words"]): void => {
    set_words(params.alert_words);
};
