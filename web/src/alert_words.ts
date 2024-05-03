import _ from "lodash";

import type {Message} from "./message_store";
import * as people from "./people";

// For simplicity, we use a list for our internal
// data, since that matches what the server sends us.
let my_watched_phrases: WatchedPhraseData[] = [];

type WatchedPhraseData = {
    watched_phrase: string;
};

export function set_watched_phrases(watched_phrases: WatchedPhraseData[]): void {
    // This module's highlighting algorithm of greedily created
    // highlight spans cannot correctly handle overlapping watched phrase
    // clauses, but processing in order from longest-to-shortest
    // reduces some symptoms of this. See #28415 for details.
    my_watched_phrases = watched_phrases;
    my_watched_phrases.sort((a, b) => b.watched_phrase.length - a.watched_phrase.length);
}

export function get_watched_phrase_data(): {watched_phrase: string}[] {
    // Returns a array of objects
    // (with each watched_phrase as value and 'word' as key to the object.)
    const watched_phrases = [];
    for (const phrase of my_watched_phrases) {
        const watched_phrase_data = {watched_phrase: phrase.watched_phrase};
        watched_phrases.push(watched_phrase_data);
    }
    return watched_phrases;
}

export function has_watched_phrase(phrase: string): boolean {
    return my_watched_phrases.some((watched_phrase) => watched_phrase.watched_phrase === phrase);
}

const watched_phrase_regex_replacements = new Map<string, string>([
    ["&", "&amp;"],
    ["<", "&lt;"],
    [">", "&gt;"],
    // Accept quotes with or without HTML escaping
    ['"', '(?:"|&quot;)'],
    ["'", "(?:'|&#39;)"],
]);

export function process_message(message: Message): void {
    // Parsing for watched phrases is expensive, so we rely on the host
    // to tell us there any watched phrases to even look for.
    if (!message.watched) {
        return;
    }

    for (const watched_phrase of my_watched_phrases) {
        const clean = _.escapeRegExp(watched_phrase.watched_phrase).replaceAll(
            /["&'<>]/g,
            (c) => watched_phrase_regex_replacements.get(c)!,
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
                // case when there is a watched phrase just before `<` or `>`.
                const check_string = pre_match + match.slice(0, -1);
                const in_tag = check_string.lastIndexOf("<") > check_string.lastIndexOf(">");
                // Matched word is inside an HTML tag so don't perform any highlighting.
                if (in_tag) {
                    return before + word + after;
                }
                return before + "<span class='watched-phrase'>" + word + "</span>" + after;
            },
        );
    }
}

export function notifies(message: Message): boolean {
    // We exclude ourselves from notifications when we type one of our own
    // watched phrases into a message, just because that can be annoying for
    // certain types of workflows where everybody on your team, including
    // yourself, sets up an watched phrase to effectively mention the team.
    return !people.is_current_user(message.sender_email) && message.watched;
}

export const initialize = (params: {watched_phrases: WatchedPhraseData[]}): void => {
    set_watched_phrases(params.watched_phrases);
};
