var settings_sections = (function () {

var exports = {};

var load_func_dict = new Dict(); // section -> function
var is_loaded = new Dict(); // section -> bool

exports.initialize = function () {
    settings_ui.initialize();
    load_func_dict.set('your-account', settings_account.set_up);
    load_func_dict.set('display-settings', settings_display.set_up);
    load_func_dict.set('notifications', settings_notifications.set_up);
    load_func_dict.set('your-bots', settings_bots.set_up);
    load_func_dict.set('alert-words', alert_words_ui.set_up_alert_words);
    load_func_dict.set('uploaded-files', attachments_ui.set_up_attachments);
    load_func_dict.set('muted-topics', settings_muting.set_up);
    load_func_dict.set('zulip-labs', settings_lab.set_up);
};

exports.load_settings_section = function (section) {
    if (!load_func_dict.has(section)) {
        blueslip.error('Unknown section ' + section);
        return;
    }

    if (is_loaded.get(section)) {
        // We only load sections once (unless somebody calls
        // reset_sections).
        return;
    }

    var load_func = load_func_dict.get(section);

    // Do the real work here!
    load_func();
    is_loaded.set(section, true);
};

exports.reset_sections = function () {
    is_loaded.clear();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_sections;
}
