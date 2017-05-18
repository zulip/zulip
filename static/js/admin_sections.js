var admin_sections = (function () {

var exports = {};

var is_loaded = new Dict(); // section -> bool

exports.load_admin_section = function (name) {
    var section;

    switch (name) {
        case 'organization-settings':
        case 'organization-permissions':
        case 'auth-methods':
            section = 'org';
            break;
        case 'emoji-settings':
            section = 'emoji';
            break;
        case 'bot-list-admin':
        case 'user-list-admin':
        case 'deactivated-users-admin':
            section = 'users';
            break;
        case 'streams-list-admin':
        case 'default-streams-list':
            section = 'streams';
            break;
        case 'filter-settings':
            section = 'filters';
            break;
        default:
            blueslip.error('Unknown admin id ' + name);
            return;
    }

    if (is_loaded.get(section)) {
        // We only load sections once (unless somebody calls
        // reset_sections).
        return;
    }

    switch (section) {
        case 'org':
            settings_org.set_up();
            break;
        case 'emoji':
            settings_emoji.set_up();
            break;
        case 'users':
            settings_users.set_up();
            break;
        case 'streams':
            settings_streams.set_up();
            break;
        case 'filters':
            settings_filters.set_up();
            break;
        default:
            blueslip.error('programming error for section ' + section);
            return;
    }

    is_loaded.set(section, true);
};

exports.reset_sections = function () {
    is_loaded.clear();
    settings_org.reset();
    settings_emoji.reset();
    settings_users.reset();
    settings_streams.reset();
    settings_filters.reset();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = admin_sections;
}
