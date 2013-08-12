var summary = (function () {

// This module has helper functions for the August 2013 message
// summarizing experiment.

var exports = {};

function mark_summarized(message) {
    if (narrow.narrowed_by_reply()) {
        // Narrowed to a topic or PM recipient
        send_summarize_in_stream(message);
    }

    if (narrow.active() && !narrow.narrowed_to_search()) {
        // Narrowed to anything except a search
        send_summarize_in_home(message);
    }
}

exports.maybe_mark_summarized = function (message) {
    if (feature_flags.summarize_read_while_narrowed) {
        mark_summarized(message);
    }
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = summary;
}
