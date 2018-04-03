var util = (function () {

var exports = {};

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
    var first;
    var last;
    var value;
    var less;
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
        less = function (a, b) { return a < b; };
    }

    var len = last - first;
    var middle;
    var step;
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

exports.same_stream_and_topic = function util_same_stream_and_topic(a, b) {
    // Streams and topics are case-insensitive.
    return ((a.stream_id === b.stream_id) &&
            (a.subject.toLowerCase() === b.subject.toLowerCase()));
};

exports.is_pm_recipient = function (email, message) {
    var recipients = message.reply_to.toLowerCase().split(',');
    return recipients.indexOf(email.toLowerCase()) !== -1;
};

exports.extract_pm_recipients = function (recipients) {
    return _.filter(recipients.split(/\s*[,;]\s*/), function (recipient) {
        return recipient.trim() !== "";
    });
};

exports.same_recipient = function util_same_recipient(a, b) {
    if ((a === undefined) || (b === undefined)) {
        return false;
    }
    if (a.type !== b.type) {
        return false;
    }

    switch (a.type) {
    case 'private':
        if (a.to_user_ids === undefined) {
            return false;
        }
        return a.to_user_ids === b.to_user_ids;
    case 'stream':
        return exports.same_stream_and_topic(a, b);
    }

    // should never get here
    return false;
};

exports.same_sender = function util_same_sender(a, b) {
    return ((a !== undefined) && (b !== undefined) &&
            (a.sender_email.toLowerCase() === b.sender_email.toLowerCase()));
};

exports.normalize_recipients = function (recipients) {
    // Converts a string listing emails of message recipients
    // into a canonical formatting: emails sorted ASCIIbetically
    // with exactly one comma and no spaces between each.
    recipients = _.map(recipients.split(','), function (s) { return s.trim(); });
    recipients = _.map(recipients, function (s) { return s.toLowerCase(); });
    recipients = _.filter(recipients, function (s) { return s.length > 0; });
    recipients.sort();
    return recipients.join(',');
};

// Avoid URI decode errors by removing characters from the end
// one by one until the decode succeeds.  This makes sense if
// we are decoding input that the user is in the middle of
// typing.
exports.robust_uri_decode = function (str) {
    var end = str.length;
    while (end > 0) {
        try {
            return decodeURIComponent(str.substring(0, end));
        } catch (e) {
            if (!(e instanceof URIError)) {
                throw e;
            }
            end -= 1;
        }
    }
    return '';
};

exports.rtrim = function (str) {
    return str.replace(/\s+$/, '');
};

// If we can, use a locale-aware sorter.  However, if the browser
// doesn't support the ECMAScript Internationalization API
// Specification, do a dumb string comparison because
// String.localeCompare is really slow.
exports.make_strcmp = function () {
    try {
        var collator = new Intl.Collator();
        return collator.compare;
    } catch (e) {
        // continue regardless of error
    }

    return function util_strcmp(a, b) {
        return (a < b ? -1 : (a > b ? 1 : 0));
    };
};
exports.strcmp = exports.make_strcmp();

exports.escape_regexp = function (string) {
    // code from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions
    // Modified to escape the ^ to appease jslint. :/
    return string.replace(/([.*+?\^=!:${}()|\[\]\/\\])/g, "\\$1");
};

exports.array_compare = function util_array_compare(a, b) {
    if (a.length !== b.length) {
        return false;
    }
    var i;
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
var unassigned_value_sentinel = {};
exports.CachedValue = function (opts) {
    this._value = unassigned_value_sentinel;
    _.extend(this, opts);
};

exports.CachedValue.prototype = {
    get: function CachedValue_get() {
        if (this._value === unassigned_value_sentinel) {
            this._value = this.compute_value();
        }
        return this._value;
    },

    reset: function CachedValue_reset() {
        this._value = unassigned_value_sentinel;
    },
};

exports.is_all_or_everyone_mentioned = function (message_content) {
    var all_everyone_re = /(^|\s)(@\*{2}(all|everyone|stream)\*{2})($|\s)/;
    return all_everyone_re.test(message_content);
};

exports.move_array_elements_to_front = function util_move_array_elements_to_front(array, selected) {
    var i;
    var selected_hash = {};
    for (i = 0; i < selected.length; i += 1) {
        selected_hash[selected[i]] = true;
    }
    var selected_elements = [];
    var unselected_elements = [];
    for (i = 0; i < array.length; i += 1) {
        if (selected_hash[array[i]]) {
            selected_elements.push(array[i]);
        } else {
            unselected_elements.push(array[i]);
        }
    }
    // Add the unselected elements after the selected ones
    return selected_elements.concat(unselected_elements);
};

// check by the userAgent string if a user's client is likely mobile.
exports.is_mobile = function () {
    var regex = "Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini";
    return new RegExp(regex, "i").test(window.navigator.userAgent);
};

exports.prefix_sort = function (query, objs, get_item) {
    // Based on Bootstrap typeahead's default sorter, but taking into
    // account case sensitivity on "begins with"
    var beginswithCaseSensitive = [];
    var beginswithCaseInsensitive = [];
    var noMatch = [];
    var obj;
    var item;
    for (var i = 0; i < objs.length; i += 1) {
        obj = objs[i];
        if (get_item) {
            item = get_item(obj);
        } else {
            item = obj;
        }
        if (item.indexOf(query) === 0) {
            beginswithCaseSensitive.push(obj);
        } else if (item.toLowerCase().indexOf(query.toLowerCase()) === 0) {
            beginswithCaseInsensitive.push(obj);
        } else {
            noMatch.push(obj);
        }
    }
    return { matches: beginswithCaseSensitive.concat(beginswithCaseInsensitive),
             rest:    noMatch };
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = util;
}
