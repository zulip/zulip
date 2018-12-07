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
    if (page_params.is_admin) {
        return true;
    }

    if (page_params.is_guest) {
        return false;
    }

    return user_groups.is_member_of(group_id, people.my_current_user_id());
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
        var pill_container = $('.pill-container[data-group-pills="' + data.id + '"]');
        var pills = user_pill.create_pills(pill_container);

        function get_pill_user_ids() {
            return user_pill.get_user_ids(pills);
        }

        var userg = $('div.user-group[id="' + data.id + '"]');
        data.members.keys().forEach(function (user_id) {
            var user = people.get_person_from_user_id(user_id);
            user_pill.append_user(user, pills);
        });

        function update_membership(group_id) {
            if (exports.can_edit(group_id)) {
                return;
            }
            userg.find('.name').attr('contenteditable', 'false');
            userg.find('.description').attr('contenteditable', 'false');
            userg.addClass('ntm');
            pill_container.find('.input').attr('contenteditable', 'false');
            pill_container.find('.input').css('display', 'none');
            pill_container.addClass('not-editable');
            pill_container.off('keydown', '.pill');
            pill_container.off('keydown', '.input');
            pill_container.off('click');
            pill_container.on('click', function (e) {
                e.stopPropagation();
            });
            pill_container.find('.pill').hover(function () {
                pill_container.find('.pill').find('.exit').css('opacity', '0.5');
            }, function () {});
        }
        update_membership(data.id);

        function is_user_group_changed() {
            var draft_group = get_pill_user_ids();
            var group_data = user_groups.get_user_group_from_id(data.id);
            var original_group = group_data.members.keys();
            var same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            var description = $('#user-groups #' + data.id + ' .description').text().trim();
            var name = $('#user-groups #' + data.id + ' .name').text().trim();
            var user_group_status = $('#user-groups #' + data.id + ' .user-group-status');

            if (user_group_status.is(':visible')) {
                return false;
            }

            if (group_data.description === description && group_data.name === name &&
                (!draft_group.length || same_groups)) {
                return false;
            }
            return true;
        }

        function update_cancel_button() {
            if (!exports.can_edit(data.id)) {
                return;
            }
            var cancel_button = $('#user-groups #' + data.id + ' .save-status.btn-danger');
            var saved_button = $('#user-groups #' + data.id + ' .save-status.sea-green');
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
            var cancel_button = $('#user-groups #' + data.id + ' .save-status.btn-danger');
            var saved_button = $('#user-groups #' + data.id + ' .save-status.sea-green');
            var save_instructions = $('#user-groups #' + data.id + ' .save-instructions');
            if (!saved_button.is(':visible')) {
                cancel_button.fadeOut(0);
                save_instructions.fadeOut(0);
                saved_button.css({display: 'inline-block', opacity: 0}).fadeTo(400, 1).delay(2000).fadeTo(400, 0);
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
                    setTimeout(show_saved_button, 200);
                },
            });
        }

        function save_name_desc() {
            var user_group_status = $('#user-groups #' + data.id + ' .user-group-status');
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
                    user_group_status.hide();
                    setTimeout(show_saved_button, 200);
                },
                error: function (xhr) {
                    var errors = JSON.parse(xhr.responseText).msg;
                    xhr.responseText = JSON.stringify({msg: errors});
                    ui_report.error(i18n.t("Failed"), xhr, user_group_status);
                    update_cancel_button();
                    $('#user-groups #' + data.id + ' .name').text(group_data.name);
                    $('#user-groups #' + data.id + ' .description').text(group_data.description);
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
            if (!exports.can_edit(data.id)) {
                return;
            }

            if (do_not_blur(class_name, event)) {
                return;
            }
            if ($(event.relatedTarget).closest('#user-groups #' + data.id) &&
                $(event.relatedTarget).closest('.save-status.btn-danger').length) {
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
        if (exports.can_edit(data.id)) {
            user_pill.set_up_typeahead_on_pills(input, pills, update_cancel_button);
        }

        (function pill_remove() {
            if (!exports.can_edit(data.id)) {
                return;
            }
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
        if (!exports.can_edit(group_id)) {
            return;
        }
        var user_group = user_groups.get_user_group_from_id(group_id);
        var btn = $(this);

        function delete_user_group() {
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
        }

        // This is mostly important for styling concerns.
        var modal_parent = $('#settings_content');

        var html_body = templates.render('confirm_delete_user', {
            group_name: user_group.name,
        });

        confirm_dialog.launch({
            parent: modal_parent,
            html_heading: i18n.t('Delete user group'),
            html_body: html_body,
            html_yes_button: i18n.t('Delete'),
            on_click: delete_user_group,
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
window.settings_user_groups = settings_user_groups;
