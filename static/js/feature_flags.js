var feature_flags = (function () {

var exports = {};

exports.load_server_counts = false;

// The features below have all settled into their final states and can
// be removed when we get a chance
exports.propagate_topic_edits = true;
exports.clicking_notification_causes_narrow = true;
exports.reminders_in_message_action_menu = true;

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = feature_flags;
}
window.feature_flags = feature_flags;
