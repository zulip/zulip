var feature_flags = (function () {

var exports = {};

// Manually-flipped debugging flags
exports.log_send_times = false;
exports.collect_send_times = false;

// Experimental modification to support much wider message views.
exports.full_width = false;

// The features below have all settled into their final states and can
// be removed when we get a chance
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
