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

exports.can_edit = function (group_id) {
   return (user_groups.is_member_of(group_id, people.my_current_user_id()));
};

exports.populate_user_groups = function () {

    var user_groups_section = $('#user-groups').expectOne();
    var user_groups_array = user_groups.get_realm_user_groups();
    var me = people.get_person_from_user_id(people.my_current_user_id());
    // We first separate out groups based on membership.
    var editable_groups = []; // Groups of which user is a member
    var non_editable_groups = []; // Groups of which user is not a member

    _.each(user_groups_array, function (user_group) {
        if (exports.can_edit(user_group.id)) {
            editable_groups.push(user_group);
        } else {
            non_editable_groups.push(user_group);
        }
    });
    // Save the length of user groups which user is member
    var editable_group_length = editable_groups.length;

    // We do the following for admin, since he/she can edit all groups.
    if (me.is_admin) {
        editable_groups = editable_groups.concat(non_editable_groups);
        non_editable_groups = [];
    }

    // At this moment, editable groups mean which can be edited and
    // non-editable groups mean which cannot be edited.

    if (editable_group_length > 0) {
        user_groups_section.append(i18n.t('<h3>Your groups</h3>'));
    } else if (user_groups_array.length > 0) {
        user_groups_section.append(i18n.t('<h3>Your groups</h3>'));
        user_groups_section.append(i18n.t('<p>You are not a part of any groups.</p>'));
    }

    function append_user(user, pills) {
        user_pill.append_person({
            pill_widget: pills,
            person: user,
        });
    }

    _.each(editable_groups, function (data) {
        // 'is_non_editable_first' parameter will hold only (if at all) in case of admins, when
        // we have groups (for 1st such group) of which admin is not a member of.
        var args = {
            name: data.name,
            id: data.id,
            description: data.description,
            is_non_member_first: editable_groups.indexOf(data) === editable_group_length,
        };
        user_groups_section.append(templates.render('admin_user_group_list', args));
        var pill_container = $('.pill-container[data-group-pills="' + data.name + '"]');
        var pills = input_pill.create({
            container: pill_container,
            create_item_from_text: user_pill.create_item_from_email,
            get_text_from_item: user_pill.get_email_from_item,
        });

        function get_pill_user_ids() {
            return user_pill.get_user_ids(pills);
        }

        data.members.keys().forEach(function (user_id) {
            var user = people.get_person_from_user_id(user_id);

            if (user) {
                append_user(user, pills);
            } else {
                blueslip.warn('Unknown user ID ' + user_id + ' in members of user group ' + data.name);
            }
        });

        function is_user_group_changed() {
            var draft_group = get_pill_user_ids();
            var group_data = user_groups.get_user_group_from_id(data.id);
            var original_group = group_data.members.keys();
            var same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            var description = $('#user-groups #' + data.id + ' .description').text().trim();
            var name = $('#user-groups #' + data.id + ' .name').text().trim();

            if ((group_data.description === description && group_data.name === name) &&
                (!draft_group.length || same_groups)) {
                return false;
            }
            return true;
        }

        function update_cancel_button() {
            var cancel_button = $('#user-groups #' + data.id + ' .cancel');
            var saved_button = $('#user-groups #' + data.id + ' .saved');
            var save_instructions = $('#user-groups #' + data.id + ' .save-instructions');

            if (is_user_group_changed() &&
               !cancel_button.is(':visible')) {
                saved_button.fadeOut(0);
                cancel_button.css({display: 'inline-block', opacity: 0}).fadeTo(400, 1);
                save_instructions.css({display: 'block', opacity: 0}).fadeTo(400, 1);
            } else if (!is_user_group_changed() &&
                cancel_button.is(':visible')) {
                    cancel_button.fadeOut();
                    save_instructions.fadeOut();
                }
        }

        function show_saved_button() {
            var cancel_button = $('#user-groups #' + data.id + ' .cancel');
            var saved_button = $('#user-groups #' + data.id + ' .saved');
            var save_instructions = $('#user-groups #' + data.id + ' .save-instructions');
            if (!saved_button.is(':visible')) {
                cancel_button.fadeOut(0);
                save_instructions.fadeOut(0);
                saved_button.css({display: 'inline-block', opacity: 0}).fadeTo(400, 1);
            }
        }

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
                success: function () {
                    show_saved_button();
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
                    setTimeout(show_saved_button, 100);
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
            if ($(event.relatedTarget).closest('#user-groups #' + data.id).length) {
                return _.some(blur_exceptions, function (class_name) {
                    return $(event.relatedTarget).closest(class_name).length;
                });
            }
            return false;
        }

        function auto_save(class_name, event) {
            if (do_not_blur(class_name, event)) {
                return;
            }
            if ($(event.relatedTarget).closest('#user-groups #' + data.id) &&
                $(event.relatedTarget).closest('.cancel').length) {
                    settings_user_groups.reload();
                    return;
            }
            save_name_desc();
            save_members();
        }

        $('#user-groups #' + data.id).on('blur', '.input', function (event) {
            auto_save('.input', event);
        });

        $('#user-groups #' + data.id).on('blur', '.name', function (event) {
            auto_save('.name', event);
        });
        $('#user-groups #' + data.id).on('input', '.name', function () {
            update_cancel_button();
        });

        $('#user-groups #' + data.id).on('blur', '.description', function (event) {
            auto_save('.description', event);
        });
        $('#user-groups #' + data.id).on('input', '.description', function () {
            update_cancel_button();
        });

        var input = pill_container.children('.input');
        (function set_up_typeahead() {
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
                    append_user(user, pills);
                    input.focus();
                    update_cancel_button();
                },
                stopAdvance: true,
            });
        }());

        (function pill_remove() {
            pills.onPillRemove(function () {
                // onPillRemove is fired before the pill is removed from
                // the DOM.
                update_cancel_button();
                setTimeout(function () {
                    input.focus();
                }, 100);
            });
        }());
    });
    if (non_editable_groups.length > 0) {
        user_groups_section.append(i18n.t('<h3>Other groups</h3>'));
    }
    // We now append non_editable_user_groups
    _.each(non_editable_groups, function (data) {
        user_groups_section.append(templates.render('non_editable_user_group', {
            user_group: {
                name: data.name,
                id: data.id,
                description: data.description,
            },
        }));
        var non_editable_pill_container = $('.pill-container[data-group-pills="' + data.name + '"]');
        var non_editable_pills = input_pill.create_non_editable_pills({
            container: non_editable_pill_container,
        });

        data.members.keys().forEach(function (user_id) {
            var user = people.get_person_from_user_id(user_id);

            if (user) {
                append_user(user, non_editable_pills);
            } else {
                blueslip.warn('Unknown user ID ' + user_id + ' in members of user group ' + data.name);
            }
        });
    });
};

exports.set_up = function () {
    meta.loaded = true;
    exports.populate_user_groups();

    $(".organization form.admin-user-group-form").off("submit").on("submit", function (e) {
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
