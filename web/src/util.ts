import _ from "lodash";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";
import type {MatchedMessage, Message, RawMessage} from "./message_store";
import type {UpdateMessageEvent} from "./types";
import {user_settings} from "./user_settings";

// From MDN: https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Math/random
export function random_int(min: number, max: number): number {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// Like C++'s std::lower_bound.  Returns the first index at which
// `value` could be inserted without changing the ordering.  Assumes
// the array is sorted.
//
// `first` and `last` are indices and `less` is an optionally-specified
// function that returns true if
//   array[i] < value
// for some i and false otherwise.
//
// Usage: lower_bound(array, value, less)
export function lower_bound<T1, T2>(
    array: T1[],
    value: T2,
    less: (item: T1, value: T2, middle: number) => boolean,
): number {
    let first = 0;
    const last = array.length;

    let len = last - first;
    let middle;
    let step;
    while (len > 0) {
        step = Math.floor(len / 2);
        middle = first + step;
        if (less(array[middle], value, middle)) {
            first = middle;
            first += 1;
            len = len - step - 1;
        } else {
            len = step;
        }
    }
    return first;
}

export const lower_same = function lower_same(a?: string, b?: string): boolean {
    if (a === undefined || b === undefined) {
        blueslip.error("Cannot compare strings; at least one value is undefined", {a, b});
        return false;
    }
    return a.toLowerCase() === b.toLowerCase();
};

export type StreamTopic = {
    stream_id: number;
    topic: string;
};

export const same_stream_and_topic = function util_same_stream_and_topic(
    a: StreamTopic,
    b: StreamTopic,
): boolean {
    // Streams and topics are case-insensitive.
    return a.stream_id === b.stream_id && lower_same(a.topic, b.topic);
};

export function extract_pm_recipients(recipients: string): string[] {
    return recipients.split(/\s*[,;]\s*/).filter((recipient) => recipient.trim() !== "");
}

// When the type is "private", properties from to_user_ids might be undefined.
// See https://github.com/zulip/zulip/pull/23032#discussion_r1038480596.
export type Recipient =
    | {type: "private"; to_user_ids?: string; reply_to: string}
    | ({type: "stream"} & StreamTopic);

export const same_recipient = function util_same_recipient(a?: Recipient, b?: Recipient): boolean {
    if (a === undefined || b === undefined) {
        return false;
    }

    if (a.type === "private" && b.type === "private") {
        if (a.to_user_ids === undefined) {
            return false;
        }
        return a.to_user_ids === b.to_user_ids;
    } else if (a.type === "stream" && b.type === "stream") {
        return same_stream_and_topic(a, b);
    }

    return false;
};

export const same_sender = function util_same_sender(a: RawMessage, b: RawMessage): boolean {
    return (
        a !== undefined &&
        b !== undefined &&
        a.sender_email.toLowerCase() === b.sender_email.toLowerCase()
    );
};

export function normalize_recipients(recipients: string): string {
    // Converts a string listing emails of message recipients
    // into a canonical formatting: emails sorted ASCIIbetically
    // with exactly one comma and no spaces between each.
    return recipients
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter((s) => s.length > 0)
        .sort()
        .join(",");
}

// Avoid URI decode errors by removing characters from the end
// one by one until the decode succeeds.  This makes sense if
// we are decoding input that the user is in the middle of
// typing.
export function robust_url_decode(str: string): string {
    let end = str.length;
    while (end > 0) {
        try {
            return decodeURIComponent(str.slice(0, end));
        } catch (error) {
            if (!(error instanceof URIError)) {
                throw error;
            }
            end -= 1;
        }
    }
    return "";
}

// If we can, use a locale-aware sorter.  However, if the browser
// doesn't support the ECMAScript Internationalization API
// Specification, do a dumb string comparison because
// String.localeCompare is really slow.
export function make_strcmp(): (x: string, y: string) => number {
    try {
        const collator = new Intl.Collator();
        return collator.compare.bind(collator);
    } catch {
        // continue regardless of error
    }

    return function util_strcmp(a: string, b: string): number {
        return a < b ? -1 : a > b ? 1 : 0;
    };
}

export const strcmp = make_strcmp();

export const array_compare = function util_array_compare<T>(a: T[], b: T[]): boolean {
    if (a.length !== b.length) {
        return false;
    }
    let i;
    for (i = 0; i < a.length; i += 1) {
        if (a[i] !== b[i]) {
            return false;
        }
    }
    return true;
};

/* Represents a value that is expensive to compute and should be
 * computed on demand and then cached.  The value can be forcefully
 * recalculated on the next call to get() by calling reset().
 *
 * You must supply a option to the constructor called compute_value
 * which should be a function that computes the uncached value.
 */
const unassigned_value_sentinel: unique symbol = Symbol("unassigned_value_sentinel");
export class CachedValue<T> {
    _value: T | typeof unassigned_value_sentinel = unassigned_value_sentinel;

    private compute_value: () => T;

    constructor(opts: {compute_value: () => T}) {
        this.compute_value = opts.compute_value;
    }

    get(): T {
        if (this._value === unassigned_value_sentinel) {
            this._value = this.compute_value();
        }
        return this._value;
    }

    reset(): void {
        this._value = unassigned_value_sentinel;
    }
}

export function find_stream_wildcard_mentions(message_content: string): string | null {
    // We cannot use the exact same regex as the server side uses (in zerver/lib/mention.py)
    // because Safari < 16.4 does not support look-behind assertions.  Reframe the lookbehind of a
    // negative character class as a start-of-string or positive character class.
    const mention = message_content.match(
        /(?:^|[\s"'(/<[{])(@\*{2}(all|everyone|stream|channel)\*{2})/,
    );
    if (mention === null) {
        return null;
    }
    return mention[2];
}

export const move_array_elements_to_front = function util_move_array_elements_to_front<T>(
    array: T[],
    selected: T[],
): T[] {
    const selected_hash = new Set(selected);
    const selected_elements: T[] = [];
    const unselected_elements: T[] = [];
    for (const element of array) {
        (selected_hash.has(element) ? selected_elements : unselected_elements).push(element);
    }
    return [...selected_elements, ...unselected_elements];
};

// check by the userAgent string if a user's client is likely mobile.
export function is_mobile(): boolean {
    return /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(
        window.navigator.userAgent,
    );
}

export function is_client_safari(): boolean {
    // Since GestureEvent is only supported on Safari, we can use it
    // to detect if the browser is Safari including Safari on iOS.
    // https://developer.mozilla.org/en-US/docs/Web/API/GestureEvent
    return "GestureEvent" in window;
}

export function sorted_ids(ids: number[]): number[] {
    // This makes sure we don't mutate the list.
    const id_list = [...new Set(ids)];
    id_list.sort((a, b) => a - b);

    return id_list;
}

export function set_match_data(target: Message, source: MatchedMessage): void {
    target.match_subject = source.match_subject;
    target.match_content = source.match_content;
}

export function get_match_topic(obj: Message): string | undefined {
    return obj.match_subject;
}

export function get_edit_event_topic(obj: UpdateMessageEvent): string | undefined {
    if (obj.topic === undefined) {
        return obj.subject;
    }

    // This code won't be reachable till we fix the
    // server, but we use it now in tests.
    return obj.topic;
}

export function get_edit_event_orig_topic(obj: UpdateMessageEvent): string | undefined {
    return obj.orig_subject;
}

export function is_topic_synonym(operator: string): boolean {
    return operator === "subject";
}

export function convert_message_topic(message: Message): void {
    if (message.type === "stream" && message.topic === undefined) {
        message.topic = message.subject;
    }
}

// TODO: When "stream" is renamed to "channel", update these stream
// synonym helper functions for the reverse logic.
export function is_stream_synonym(text: string): boolean {
    return text === "channel";
}

export function is_streams_synonym(text: string): boolean {
    return text === "channels";
}

// For parts of the codebase that have been converted to use
// channel/channels internally, this is used to convert those
// back into stream/streams for external presentation.
export function canonicalize_stream_synonyms(text: string): string {
    if (is_stream_synonym(text.toLowerCase())) {
        return "stream";
    }
    if (is_streams_synonym(text.toLowerCase())) {
        return "streams";
    }
    return text;
}

let inertDocument: Document | undefined;

export function clean_user_content_links(html: string): string {
    if (inertDocument === undefined) {
        inertDocument = new DOMParser().parseFromString("", "text/html");
    }
    const template = inertDocument.createElement("template");
    template.innerHTML = html;

    for (const elt of template.content.querySelectorAll("a")) {
        // Ensure that all external links have target="_blank"
        // rel="opener noreferrer".  This ensures that external links
        // never replace the Zulip web app while also protecting
        // against reverse tabnapping attacks, without relying on the
        // correctness of how Zulip's Markdown processor generates links.
        //
        // Fragment links, which we intend to only open within the
        // Zulip web app using our hashchange system, do not require
        // these attributes.
        const href = elt.getAttribute("href");
        if (href === null) {
            continue;
        }
        let url;
        try {
            url = new URL(href, window.location.href);
        } catch {
            elt.removeAttribute("href");
            elt.removeAttribute("title");
            continue;
        }

        // eslint-disable-next-line no-script-url
        if (["data:", "javascript:", "vbscript:"].includes(url.protocol)) {
            // Remove unsafe links completely.
            elt.removeAttribute("href");
            elt.removeAttribute("title");
            continue;
        }

        // We detect URLs that are just fragments by comparing the URL
        // against a new URL generated using only the hash.
        if (url.hash === "" || url.href !== new URL(url.hash, window.location.href).href) {
            elt.setAttribute("target", "_blank");
            elt.setAttribute("rel", "noopener noreferrer");
        } else {
            elt.removeAttribute("target");
        }

        if (elt.parentElement?.classList.contains("message_inline_image")) {
            // For inline images we want to handle the tooltips explicitly, and disable
            // the browser's built in handling of the title attribute.
            const title = elt.getAttribute("title");
            if (title !== null) {
                elt.setAttribute("aria-label", title);
                elt.removeAttribute("title");
            }
        } else {
            // For non-image user uploads, the following block ensures that the title
            // attribute always displays the filename as a security measure.
            let title: string;
            let legacy_title: string;
            if (
                url.origin === window.location.origin &&
                url.pathname.startsWith("/user_uploads/")
            ) {
                // We add the word "download" to make clear what will
                // happen when clicking the file.  This is particularly
                // important in the desktop app, where hovering a URL does
                // not display the URL like it does in the web app.
                title = legacy_title = $t(
                    {defaultMessage: "Download {filename}"},
                    {filename: url.pathname.slice(url.pathname.lastIndexOf("/") + 1)},
                );
            } else {
                title = url.toString();
                legacy_title = href;
            }
            elt.setAttribute(
                "title",
                ["", legacy_title].includes(elt.title) ? title : `${title}\n${elt.title}`,
            );
        }
    }
    return template.innerHTML;
}

export function filter_by_word_prefix_match<T>(
    items: T[],
    search_term: string,
    item_to_text: (item: T) => string,
    word_separator_regex = /\s/,
): T[] {
    if (search_term === "") {
        return items;
    }

    let search_terms = search_term.toLowerCase().split(",");
    search_terms = search_terms.map((s) => s.trim());

    const filtered_items = items.filter((item) =>
        search_terms.some((search_term) => {
            const lower_name = item_to_text(item).toLowerCase();
            // returns true if the item starts with the search term or if the
            // search term with a word separator right before it appears in the item
            return (
                lower_name.startsWith(search_term) ||
                new RegExp(word_separator_regex.source + _.escapeRegExp(search_term)).test(
                    lower_name,
                )
            );
        }),
    );

    return filtered_items;
}

export function get_time_from_date_muted(date_muted: number | undefined): number {
    if (date_muted === undefined) {
        return Date.now();
    }
    return date_muted * 1000;
}

export function call_function_periodically(callback: () => void, delay: number): void {
    // We previously used setInterval for this purpose, but
    // empirically observed that after unsuspend, Chrome can end
    // up trying to "catch up" by doing dozens of these requests
    // at once, wasting resources as well as hitting rate limits
    // on the server. We have not been able to reproduce this
    // reliably enough to be certain whether the setInterval
    // requests are those that would have happened while the
    // laptop was suspended or during a window after unsuspend
    // before the user focuses the browser tab.

    // But using setTimeout this instead ensures that we're only
    // scheduling a next call if the browser will actually be
    // calling "callback".
    setTimeout(() => {
        call_function_periodically(callback, delay);

        // Do the callback after scheduling the next call, so that we
        // are certain to call it again even if the callback throws an
        // exception.
        callback();
    }, delay);
}

export function get_string_diff(string1: string, string2: string): [number, number, number] {
    // This function specifies the single minimal diff between 2 strings. For
    // example, the diff between "#ann is for updates" and "#**announce** is
    // for updates" is from index 1, till 4 in the 1st string and 13 in the
    // 2nd string;

    let diff_start_index = -1;
    for (let i = 0; i < Math.min(string1.length, string2.length); i += 1) {
        if (string1.charAt(i) === string2.charAt(i)) {
            diff_start_index = i;
        } else {
            break;
        }
    }
    diff_start_index += 1;

    if (string1.length === string2.length && string1.length === diff_start_index) {
        // if the 2 strings are identical
        return [0, 0, 0];
    }

    let diff_end_1_index = string1.length;
    let diff_end_2_index = string2.length;
    for (
        let i = string1.length - 1, j = string2.length - 1;
        i >= diff_start_index && j >= diff_start_index;
        i -= 1, j -= 1
    ) {
        if (string1.charAt(i) === string2.charAt(j)) {
            diff_end_1_index = i;
            diff_end_2_index = j;
        } else {
            break;
        }
    }

    return [diff_start_index, diff_end_1_index, diff_end_2_index];
}

export function try_parse_as_truthy<T>(val: (T | undefined)[]): T[] | undefined {
    // This is a typesafe helper to narrow an array from containing
    // possibly falsy values into an array containing non-undefined
    // items or undefined when any of the items is falsy.

    // While this eliminates the possibility of returning an array
    // with falsy values, the type annotation does not provide that
    // guarantee. Ruling out undefined values is sufficient for the
    // helper's usecases.
    const result: T[] = [];
    for (const x of val) {
        if (!x) {
            return undefined;
        }
        result.push(x);
    }
    return result;
}

export function is_valid_url(url: string, require_absolute = false): boolean {
    try {
        let base_url;
        if (!require_absolute) {
            base_url = window.location.origin;
        }

        // JavaScript only requires the base element if we provide a relative URL.
        // If we don’t provide one, it defaults to undefined. Alternatively, if we
        // provide a base element with an absolute URL, JavaScript ignores the base element.
        new URL(url, base_url);
    } catch (error) {
        blueslip.log(`Invalid URL: ${url}.`, error);
        return false;
    }
    return true;
}

// Formats an array of strings as a Internationalized list using the specified language.
export function format_array_as_list(
    array: string[],
    style: Intl.ListFormatStyle,
    type: Intl.ListFormatType,
): string {
    // If Intl.ListFormat is not supported
    if (Intl.ListFormat === undefined) {
        return array.join(", ");
    }

    // Use Intl.ListFormat to format the array as a Internationalized list.
    const list_formatter = new Intl.ListFormat(user_settings.default_language, {style, type});

    // Return the formatted string.
    return list_formatter.format(array);
}
