var settings_user_groups = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.reload = function () {
    var user_groups_section = $('#user-groups').expectOne();
    user_groups_section.html('');
    exports.populate_user_groups();
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

        function update_save_state(draft_group) {
            var original_group = data.members;
            var same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            var save_changes = pill_container.siblings('.save-changes');
            var save_hidden = save_changes.css('display') === 'none';

            if ((!draft_group.length || same_groups) && !save_hidden) {
                save_changes.fadeOut();
            } else if (!same_groups && draft_group.length && save_hidden) {
                save_changes.css({display: 'inline-block', opacity: '0'}).fadeTo(400, 1);
            }
        }

        pills.onPillCreate(function (value, reject) {
            var person = people.get_by_email(value);
            var draft_group = pills.keys();

            if (!person || draft_group.includes(person.user_id)) {
                return reject();
            }

            draft_group.push(person.user_id);
            update_save_state(draft_group);

            return { key: person.user_id, value: person.full_name };
        });

        pills.onPillRemove(function () {
            update_save_state(pills.keys());
        });
    });
};

exports.set_up = function () {
    meta.loaded = true;

    exports.populate_user_groups();

    $(".organization").on("submit", "form.admin-user-group-form", function (e) {
        e.preventDefault();
        e.stopPropagation();

        var user_group_status = $('#admin-user-group-status');

        var group = {
            members: JSON.stringify([people.my_current_user_id()]),
        };
        _.each($(this).serializeArray(), function (obj) {
            if (obj.value.trim() === "") {
                return;
            }
            group[obj.name] = obj.value;
        });

        channel.post({
            url: "/json/user_groups/create",
            data: group,
            success: function () {
                user_group_status.hide();
                ui_report.success(i18n.t("User group added!"), user_group_status);
                $("form.admin-user-group-form input[type='text']").val("");
            },
            error: function (xhr) {
                user_group_status.hide();
                var errors = JSON.parse(xhr.responseText).msg;
                xhr.responseText = JSON.stringify({msg: errors});
                ui_report.error(i18n.t("Failed"), xhr, user_group_status);
            },
        });
    });

    $('#user-groups').on('click', '.delete', function () {
        var group_id = $(this).parent().attr('id');
        var user_group = user_groups.get_user_group_from_id(group_id);
        var btn = $(this);

        channel.del({
            url: "/json/user_groups/" + group_id,
            data: {
                id: group_id,
            },
            success: function () {
                user_groups.remove(user_group);
                settings_user_groups.reload();
            },
            error: function () {
                btn.text(i18n.t("Failed!"));
            },
        });
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_user_groups;
}
