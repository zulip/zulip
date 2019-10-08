var settings_sections = (function () {

var exports = {};

var load_func_dict = new Dict(); // group -> function
var is_loaded = new Dict(); // group -> bool

exports.get_group = function (section) {
    // Sometimes several sections all share the same code.

    switch (section) {
    case 'organization-profile':
    case 'organization-settings':
    case 'organization-permissions':
    case 'auth-methods':
        return 'org_misc';

    case 'bot-list-admin':
    case 'user-list-admin':
    case 'deactivated-users-admin':
        return 'org_users';

    default:
        return section;
    }
};

exports.initialize = function () {
    // personal
    load_func_dict.set('your-account', settings_account.set_up);
    load_func_dict.set('display-settings', settings_display.set_up);
    load_func_dict.set('notifications', settings_notifications.set_up);
    load_func_dict.set('your-bots', settings_bots.set_up);
    load_func_dict.set('alert-words', alert_words_ui.set_up_alert_words);
    load_func_dict.set('uploaded-files', attachments_ui.set_up_attachments);
    load_func_dict.set('muted-topics', settings_muting.set_up);

    // org
    load_func_dict.set('org_misc', settings_org.set_up);
    load_func_dict.set('org_users', settings_users.set_up);
    load_func_dict.set('emoji-settings', settings_emoji.set_up);
    load_func_dict.set('default-streams-list', settings_streams.set_up);
    load_func_dict.set('filter-settings', settings_linkifiers.set_up);
    load_func_dict.set('invites-list-admin', settings_invites.set_up);
    load_func_dict.set('user-groups-admin', settings_user_groups.set_up);
    load_func_dict.set('profile-field-settings', settings_profile_fields.set_up);
};

exports.load_settings_section = function (section) {
    var group = exports.get_group(section);

    if (!load_func_dict.has(group)) {
        blueslip.error('Unknown section ' + section);
        return;
    }

    if (is_loaded.get(group)) {
        // We only load groups once (unless somebody calls
        // reset_sections).
        return;
    }

    var load_func = load_func_dict.get(group);

    // Do the real work here!
    load_func();
    is_loaded.set(group, true);
};

exports.reset_sections = function () {
    is_loaded.clear();
    settings_emoji.reset();
    settings_linkifiers.reset();
    settings_invites.reset();
    settings_org.reset();
    settings_profile_fields.reset();
    settings_streams.reset();
    settings_user_groups.reset();
    settings_users.reset();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_sections;
}
window.settings_sections = settings_sections;
