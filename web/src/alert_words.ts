import _ from "lodash";

import type {Message} from "./message_store.ts";
import * as message_store from "./message_store.ts";
import * as people from "./people.ts";
import type {StateData, WatchedPhrase} from "./state_data.ts";

// For simplicity, we use a list for our internal
// data, since that matches what the server sends us.
let my_watched_phrases: WatchedPhrase[] = [];
let my_alert_words: string[] = [];

export function set_watched_phrases(watched_phrases: WatchedPhrase[]): void {
    my_watched_phrases = watched_phrases;
    // This module's highlighting algorithm of greedily created
    // highlight spans cannot correctly handle overlapping alert word
    // clauses, but processing in order from longest-to-shortest
    // reduces some symptoms of this. See #28415 for details.
    my_alert_words = watched_phrases.map((phrase) => phrase.watched_phrase);
    my_alert_words.sort((a, b) => b.length - a.length);
}

export function get_word_list(): {word: string; automatically_follow_topics: boolean}[] {
    // Returns an array of objects, one per alert word, with the word
    // itself under the 'word' key.
    return my_watched_phrases.map((phrase) => ({
        word: phrase.watched_phrase,
        automatically_follow_topics: phrase.automatically_follow_topics,
    }));
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

export function highlight_alert_words(content: string): string {
    let updated_content = content;

    for (const word of my_alert_words) {
        const clean = _.escapeRegExp(word).replaceAll(/["&'<>]/g, (c) =>
            alert_regex_replacements.get(c)!,
        );
        const before_punctuation = "\\s|^|>|[\\(\\\".,';\\[]";
        const after_punctuation = "(?=\\s)|$|<|[\\)\\\"\\?!:.,';\\]!]";

        const regex = new RegExp(`(${before_punctuation})(${clean})(${after_punctuation})`, "ig");
        updated_content = updated_content.replace(
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

    return updated_content;
}

export function process_message(message: Message): void {
    // Parsing for alert words is expensive, so we rely on the host
    // to tell us if there are any alert words to even look for.
    if (!message.alerted) {
        return;
    }

    const updated_content = highlight_alert_words(message.content);
    message_store.update_message_content(message, updated_content);
}

export function notifies(message: Message): boolean {
    // We exclude ourselves from notifications when we type one of our own
    // alert words into a message, just because that can be annoying for
    // certain types of workflows where everybody on your team, including
    // yourself, sets up an alert word to effectively mention the team.
    return !people.is_my_user_id(message.sender_id) && message.alerted;
}

export const initialize = (params: StateData["alert_words"]): void => {
    set_watched_phrases(params.watched_phrases);
};
