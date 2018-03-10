var settings_user_groups = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.reload = function () {
    if (!meta.loaded) {
        return;
    }

    var user_groups_section = $('#user-groups').expectOne();
    user_groups_section.html('');
    exports.populate_user_groups();
};

exports.populate_user_groups = function () {
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
        var pills = input_pill.create({
            container: pill_container,
            create_item_from_text: user_pill.create_item_from_email,
            get_text_from_item: user_pill.get_email_from_item,
        });

        function get_pill_user_ids() {
            return user_pill.get_user_ids(pills);
        }

        function append_user(user) {
            user_pill.append_person({
                pill_widget: pills,
                person: user,
            });
        }

        data.members.keys().forEach(function (user_id) {
            var user = people.get_person_from_user_id(user_id);

            if (user) {
                append_user(user);
            } else {
                blueslip.warn('Unknown user ID ' + user_id + ' in members of user group ' + data.name);
            }
        });

        function update_save_state() {
            var draft_group = get_pill_user_ids();
            var original_group = user_groups.get_user_group_from_id(data.id).members.keys();
            var same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            var save_changes = pill_container.siblings('.save-member-changes');
            var save_hidden = save_changes.css('display') === 'none';

            if ((!draft_group.length || same_groups) && !save_hidden) {
                save_changes.fadeOut();
            } else if (!same_groups && draft_group.length && save_hidden) {
                save_changes.css({display: 'inline-block', opacity: '0'}).fadeTo(400, 1);
            }
        }

        var input = pill_container.children('.input');

        (function set_up_typeahead() {
            // We will early-exit here in a later commit.
            input.typeahead({
                items: 5,
                fixed: true,
                dropup: true,
                source: function () {
                    return user_pill.typeahead_source(pills);
                },
                highlighter: function (item) {
                    return typeahead_helper.render_person(item);
                },
                matcher: function (item) {
                    var query = this.query.toLowerCase();
                    return (item.email.toLowerCase().indexOf(query) !== -1
                            || item.full_name.toLowerCase().indexOf(query) !== -1);
                },
                sorter: function (matches) {
                    return typeahead_helper.sort_recipientbox_typeahead(
                        this.query, matches, "");
                },
                updater: function (user) {
                    append_user(user);
                    update_save_state();
                },
                stopAdvance: true,
            });
        }());

        pills.onPillCreate(function () {
            update_save_state();
        });

        pills.onPillRemove(function () {
            update_save_state();
        });

        $('#user-groups #' + data.id).on('click', '.save-member-changes', function () {
            var draft_group = get_pill_user_ids();
            var group_data = user_groups.get_user_group_from_id(data.id);
            var original_group = group_data.members.keys();
            var added = _.difference(draft_group, original_group);
            var removed = _.difference(original_group, draft_group);
            var btn = $(this);

            channel.post({
                url: "/json/user_groups/" + data.id + '/members',
                data: {
                    add: JSON.stringify(added),
                    delete: JSON.stringify(removed),
                },
                success: function () {
                    btn.text(i18n.t("Saved!")).delay(200).fadeOut(function () {
                        $(this).html('<i class="fa fa-check" aria-hidden="true"></i>');
                    });
                },
                error: function () {
                    btn.text(i18n.t("Failed!"));
                },
            });
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
        var group_id = $(this).parents('.user-group').attr('id');
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

    $('#user-groups').on('keypress', '.user-group h4 > span', function (e) {
        if (e.which === 13) {
            e.preventDefault();
        }
    });

    $('#user-groups').on('input', '.user-group h4 > span', function () {
        var element = this.className;
        var current_text = $(this).text();
        var sibling_element = $(this).siblings('span').first().attr('class');
        var sibling_text = $(this).siblings('span').first().text();
        var group_id = $(this).parents('.user-group').attr('id');
        var user_group = user_groups.get_user_group_from_id(group_id);
        var saved_text = user_group[element];
        var saved_sibling_text = user_group[sibling_element];

        var has_changes = saved_text !== current_text || saved_sibling_text !== sibling_text;
        var save_changes = $(this).siblings('.save-group-changes');
        var save_hidden = save_changes.css('display') === 'none';
        var has_content = current_text.trim() !== '' && sibling_text.trim() !== '';

        if (has_changes && save_hidden && has_content) {
            save_changes.css({display: 'inline', opacity: '0'}).fadeTo(400, 1);
        } else if ((!has_changes || !has_content) && !save_hidden) {
            save_changes.fadeOut();
        }
    });

    $('#user-groups').on('click', '.save-group-changes', function () {
        var group_id = $(this).parents('.user-group').attr('id');
        var group_data = user_groups.get_user_group_from_id(group_id);

        var description = $(this).siblings('.description').text().trim();
        var name = $(this).siblings('.name').text().trim();
        var btn = $(this);

        channel.patch({
            url: "/json/user_groups/" + group_id,
            data: {
                name: name,
                description: description,
            },
            success: function () {
                user_groups.remove(group_data);
                group_data.description = description;
                group_data.name = name;
                user_groups.add(group_data);
                btn.text(i18n.t("Saved!")).delay(200).fadeOut(function () {
                    $(this).html('<i class="fa fa-check" aria-hidden="true"></i>');
                });
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
