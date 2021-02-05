"use strict";

const _ = require("lodash");
// From MDN: https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Math/random
exports.random_int = function random_int(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

// Like C++'s std::lower_bound.  Returns the first index at which
// `value` could be inserted without changing the ordering.  Assumes
// the array is sorted.
//
// `first` and `last` are indices and `less` is an optionally-specified
// function that returns true if
//   array[i] < value
// for some i and false otherwise.
//
// Usage: lower_bound(array, value, [less])
//        lower_bound(array, first, last, value, [less])
exports.lower_bound = function (array, arg1, arg2, arg3, arg4) {
    let first;
    let last;
    let value;
    let less;
    if (arg3 === undefined) {
        first = 0;
        last = array.length;
        value = arg1;
        less = arg2;
    } else {
        first = arg1;
        last = arg2;
        value = arg3;
        less = arg4;
    }

    if (less === undefined) {
        less = function (a, b) {
            return a < b;
        };
    }

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
};

function lower_same(a, b) {
    return a.toLowerCase() === b.toLowerCase();
}

exports.same_stream_and_topic = function util_same_stream_and_topic(a, b) {
    // Streams and topics are case-insensitive.
    return a.stream_id === b.stream_id && lower_same(a.topic, b.topic);
};

exports.is_pm_recipient = function (user_id, message) {
    const recipients = message.to_user_ids.split(",");
    return recipients.includes(user_id.toString());
};

exports.extract_pm_recipients = function (recipients) {
    return recipients.split(/\s*[,;]\s*/).filter((recipient) => recipient.trim() !== "");
};

exports.same_recipient = function util_same_recipient(a, b) {
    if (a === undefined || b === undefined) {
        return false;
    }
    if (a.type !== b.type) {
        return false;
    }

    switch (a.type) {
        case "private":
            if (a.to_user_ids === undefined) {
                return false;
            }
            return a.to_user_ids === b.to_user_ids;
        case "stream":
            return exports.same_stream_and_topic(a, b);
    }

    // should never get here
    return false;
};

exports.same_sender = function util_same_sender(a, b) {
    return (
        a !== undefined &&
        b !== undefined &&
        a.sender_email.toLowerCase() === b.sender_email.toLowerCase()
    );
};

exports.normalize_recipients = function (recipients) {
    // Converts a string listing emails of message recipients
    // into a canonical formatting: emails sorted ASCIIbetically
    // with exactly one comma and no spaces between each.
    recipients = recipients.split(",").map((s) => s.trim());
    recipients = recipients.map((s) => s.toLowerCase());
    recipients = recipients.filter((s) => s.length > 0);
    recipients.sort();
    return recipients.join(",");
};

// Avoid URI decode errors by removing characters from the end
// one by one until the decode succeeds.  This makes sense if
// we are decoding input that the user is in the middle of
// typing.
exports.robust_uri_decode = function (str) {
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
};

// If we can, use a locale-aware sorter.  However, if the browser
// doesn't support the ECMAScript Internationalization API
// Specification, do a dumb string comparison because
// String.localeCompare is really slow.
exports.make_strcmp = function () {
    try {
        const collator = new Intl.Collator();
        return collator.compare;
    } catch {
        // continue regardless of error
    }

    return function util_strcmp(a, b) {
        return a < b ? -1 : a > b ? 1 : 0;
    };
};
exports.strcmp = exports.make_strcmp();

exports.array_compare = function util_array_compare(a, b) {
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
const unassigned_value_sentinel = {};
class CachedValue {
    _value = unassigned_value_sentinel;

    constructor(opts) {
        Object.assign(this, opts);
    }

    get() {
        if (this._value === unassigned_value_sentinel) {
            this._value = this.compute_value();
        }
        return this._value;
    }

    reset() {
        this._value = unassigned_value_sentinel;
    }
}
exports.CachedValue = CachedValue;

exports.find_wildcard_mentions = function (message_content) {
    const mention = message_content.match(/(^|\s)(@\*{2}(all|everyone|stream)\*{2})($|\s)/);
    if (mention === null) {
        return null;
    }
    return mention[3];
};

exports.move_array_elements_to_front = function util_move_array_elements_to_front(array, selected) {
    const selected_hash = new Set(selected);
    const selected_elements = [];
    const unselected_elements = [];
    for (const element of array) {
        (selected_hash.has(element) ? selected_elements : unselected_elements).push(element);
    }
    return [...selected_elements, ...unselected_elements];
};

// check by the userAgent string if a user's client is likely mobile.
exports.is_mobile = function () {
    const regex = "Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini";
    return new RegExp(regex, "i").test(window.navigator.userAgent);
};

exports.sorted_ids = function (ids) {
    // This mapping makes sure we are using ints, and
    // it also makes sure we don't mutate the list.
    let id_list = ids.map((s) => Number.parseInt(s, 10));
    id_list.sort((a, b) => a - b);
    id_list = _.sortedUniq(id_list);

    return id_list;
};

exports.set_match_data = function (target, source) {
    target.match_subject = source.match_subject;
    target.match_content = source.match_content;
};

exports.get_match_topic = function (obj) {
    return obj.match_subject;
};

exports.get_draft_topic = function (obj) {
    // We will need to support subject for old drafts.
    return obj.topic || obj.subject || "";
};

exports.get_reload_topic = function (obj) {
    // When we first upgrade to releases that have
    // topic=foo in the code, the user's reload URL
    // may still have subject=foo from the prior version.
    return obj.topic || obj.subject || "";
};

exports.get_edit_event_topic = function (obj) {
    if (obj.topic === undefined) {
        return obj.subject;
    }

    // This code won't be reachable till we fix the
    // server, but we use it now in tests.
    return obj.topic;
};

exports.get_edit_event_orig_topic = function (obj) {
    return obj.orig_subject;
};

exports.get_edit_event_prev_topic = function (obj) {
    return obj.prev_subject;
};

exports.is_topic_synonym = function (operator) {
    return operator === "subject";
};

exports.convert_message_topic = function (message) {
    if (message.topic === undefined) {
        message.topic = message.subject;
    }
};

exports.clean_user_content_links = function (html) {
    const content = new DOMParser().parseFromString(html, "text/html").body;
    for (const elt of content.querySelectorAll("a")) {
        // Ensure that all external links have target="_blank"
        // rel="opener noreferrer".  This ensures that external links
        // never replace the Zulip webapp while also protecting
        // against reverse tabnapping attacks, without relying on the
        // correctness of how Zulip's Markdown processor generates links.
        //
        // Fragment links, which we intend to only open within the
        // Zulip webapp using our hashchange system, do not require
        // these attributes.
        const href = elt.getAttribute("href");
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

        // Ensure that the title displays the real URL.
        let title;
        let legacy_title;
        if (url.origin === window.location.origin && url.pathname.startsWith("/user_uploads/")) {
            title = legacy_title = url.pathname.slice(url.pathname.lastIndexOf("/") + 1);
        } else {
            title = url;
            legacy_title = href;
        }
        elt.setAttribute(
            "title",
            ["", legacy_title].includes(elt.title) ? title : `${title}\n${elt.title}`,
        );
    }
    return content.innerHTML;
};
