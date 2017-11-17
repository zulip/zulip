var settings_user_groups = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.populate_user_groups = function () {
    if (!meta.loaded) {
        return;
    }

    var user_groups_section = $('#user-groups').expectOne();
    var user_groups_array = user_groups.get_realm_user_groups();

    _.each(user_groups_array, function (data) {
        user_groups_section.append(templates.render('admin_user_group_list', {
            user_group: {
                name: data.name,
                id: data.id,
                description: data.description,
            },
        }));

        var pill_container = $('.pill-container[data-group-pills="' + data.name + '"]');
        var pills = input_pill(pill_container);
        data.members.forEach(function (user_id) {
            var user = people.get_person_from_user_id(user_id);

            if (user) {
                pills.pill.append(user.full_name, user_id);
            } else {
                blueslip.warn('Unknown user ID ' + user_id + ' in members of user group ' + data.name);
            }
        });
    });

};

exports.set_up = function () {
    meta.loaded = true;

    exports.populate_user_groups();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_user_groups;
}
