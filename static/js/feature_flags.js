var feature_flags = (function () {

var exports = {};

// Manually-flipped debugging flags
exports.log_send_times = false;
exports.collect_send_times = false;
exports.local_echo = true;

// Experimental modification to support much wider message views.
exports.full_width = false;

// Beta rewrite of the Bot UI; probably worth finishing and deploying
exports.new_bot_ui = false;

// Experimental feature to not fade messages that differ only in
// topic; was not a successful experiment so can be deleted.
exports.fade_at_stream_granularity = false;

// The features below have all settled into their final states and can
// be removed when we get a chance
exports.cleanup_before_reload = true;
exports.fade_users_when_composing = true;
exports.mark_read_at_bottom = true;
exports.propagate_topic_edits = true;
exports.clicking_notification_causes_narrow = true;
exports.collapsible = false;
exports.dropbox_integration = false;

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = feature_flags;
}
