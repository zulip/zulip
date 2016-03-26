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
    var first, last, value, less;
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
    var lower = 0;
    while (len > 0) {
        step = Math.floor(len / 2);
        middle = first + step;
        if (less(array[middle], value, middle)) {
            first = middle;
            first++;
            len = len - step - 1;
        }
        else {
            len = step;
        }
    }
    return first;
};

exports.same_stream_and_subject = function util_same_stream_and_subject(a, b) {
    // Streams and subjects are case-insensitive.
    return ((a.stream.toLowerCase() === b.stream.toLowerCase()) &&
            (a.subject.toLowerCase() === b.subject.toLowerCase()));
};

exports.same_major_recipient = function (a, b) {
    // Same behavior as same_recipient, except that it returns true for messages
    // on different topics but the same stream.
    if ((a === undefined) || (b === undefined)) {
        return false;
    }
    if (a.type !== b.type) {
        return false;
    }

    switch (a.type) {
    case 'private':
        return a.reply_to.toLowerCase() === b.reply_to.toLowerCase();
    case 'stream':
        return a.stream.toLowerCase() === b.stream.toLowerCase();
    }

    // should never get here
    return false;
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
        return a.reply_to.toLowerCase() === b.reply_to.toLowerCase();
    case 'stream':
        return exports.same_stream_and_subject(a, b);
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
    recipients = _.map(recipients.split(','), $.trim);
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
            end--;
        }
    }
    return '';
};

// If we can, use a locale-aware sorter.  However, if the browser
// doesn't support the ECMAScript Internationalization API
// Specification, do a dumb string comparison because
// String.localeCompare is really slow.
exports.strcmp = (function () {
    try {
        var collator = new Intl.Collator();
        return collator.compare;
    } catch (e) {
    }

    return function util_strcmp (a, b) {
        return (a < b ? -1 : (a > b ? 1 : 0));
    };
}());

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
    for (i = 0; i < a.length; ++i) {
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
    }
};

exports.enforce_arity = function util_enforce_arity(func) {
    return function () {
        if (func.length !== arguments.length) {
            throw new Error("Function '" + func.name + "' called with "
                            + arguments.length + " arguments, but expected "
                            + func.length);
        }
        return func.apply(this, arguments);
    };
};

exports.execute_early = function (func) {
    if (page_params.test_suite) {
        $(document).one('phantom_page_loaded', func);
    } else {
        $(func);
    }
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = util;
}
