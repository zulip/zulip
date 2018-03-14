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

        function save_members() {
            var draft_group = get_pill_user_ids();
            var group_data = user_groups.get_user_group_from_id(data.id);
            var original_group = group_data.members.keys();
            var same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            if (!draft_group.length || same_groups) {
                return;
            }

            var added = _.difference(draft_group, original_group);
            var removed = _.difference(original_group, draft_group);
            channel.post({
                url: "/json/user_groups/" + data.id + '/members',
                data: {
                    add: JSON.stringify(added),
                    delete: JSON.stringify(removed),
                },
            });
        }

        function save_name_desc() {
            var group_data = user_groups.get_user_group_from_id(data.id);
            var description = $('#user-groups #' + data.id + ' .description').text().trim();
            var name = $('#user-groups #' + data.id + ' .name').text().trim();

            if (group_data.description === description && group_data.name === name) {
                return;
            }

            channel.patch({
                url: "/json/user_groups/" + data.id,
                data: {
                    name: name,
                    description: description,
                },
                success: function () {
                },
            });
        }

        function do_not_blur(except_class, event) {
            // Event generated from or inside the typeahead.
            if ($(event.relatedTarget).closest(".typeahead").length) {
                return true;
            }

            var blur_exceptions = _.without([".pill-container", ".name", ".description", ".input", ".delete"],
                                            except_class);
            if ($(event.relatedTarget).parents('#user-groups #' + data.id)) {
                return _.some(blur_exceptions, function (class_name) {
                    return $(event.relatedTarget).closest(class_name).length;
                });
            }
            return false;
        }

        $('#user-groups #' + data.id).on('blur', '.input', function (event) {
            if (do_not_blur('.input', event)) {
                return;
            }
            save_name_desc();
            save_members();
        });

        $('#user-groups #' + data.id).on('blur', '.name', function (event) {
            if (do_not_blur('.name', event)) {
                return;
            }
            save_name_desc();
            save_members();
        });

        $('#user-groups #' + data.id).on('blur', '.description', function (event) {
            if (do_not_blur('.description', event)) {
                return;
            }
            save_name_desc();
            save_members();
        });

        var input = pill_container.children('.input');

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
                input.focus();
            },
            stopAdvance: true,
        });

        pills.onPillRemove(function () {
            // onPillRemove is fired before the pill is removed from
            // the DOM.
            setTimeout(function () {
                input.focus();
            }, 100);
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
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_user_groups;
}
