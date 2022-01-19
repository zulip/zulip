import $ from "jquery";
import _ from "lodash";

import render_confirm_delete_user from "../templates/confirm_dialog/confirm_delete_user.hbs";
import render_admin_user_group_list from "../templates/settings/admin_user_group_list.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t, $t_html} from "./i18n";
import {page_params} from "./page_params";
import * as people from "./people";
import * as pill_typeahead from "./pill_typeahead";
import * as settings_data from "./settings_data";
import * as ui_report from "./ui_report";
import * as user_groups from "./user_groups";
import * as user_pill from "./user_pill";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

export function reload() {
    if (!meta.loaded) {
        return;
    }

    const user_groups_section = $("#user-groups").expectOne();
    user_groups_section.html("");
    populate_user_groups();
}

export function can_edit(group_id) {
    if (!settings_data.user_can_edit_user_groups()) {
        return false;
    }

    // Admins and moderators are allowed to edit user groups even if they
    // are not a member of that user group. Members can edit user groups
    // only if they belong to that group.
    if (page_params.is_admin || page_params.is_moderator) {
        return true;
    }

    return user_groups.is_member_of(group_id, people.my_current_user_id());
}

export function populate_user_groups() {
    const user_groups_section = $("#user-groups").expectOne();
    const user_groups_array = user_groups.get_realm_user_groups();

    for (const data of user_groups_array) {
        user_groups_section.append(
            render_admin_user_group_list({
                user_group: {
                    name: data.name,
                    id: data.id,
                    description: data.description,
                },
            }),
        );
        const pill_container = $(`.pill-container[data-group-pills="${CSS.escape(data.id)}"]`);
        const pills = user_pill.create_pills(pill_container);

        function get_pill_user_ids() {
            return user_pill.get_user_ids(pills);
        }

        const userg = $(`div.user-group[id="${CSS.escape(data.id)}"]`);
        for (const user_id of data.members) {
            const user = people.get_by_user_id(user_id);
            user_pill.append_user(user, pills);
        }

        function update_membership(group_id) {
            if (can_edit(group_id)) {
                return;
            }
            userg.find(".name").attr("contenteditable", "false");
            userg.find(".description").attr("contenteditable", "false");
            userg.addClass("ntm");
            pill_container.find(".input").attr("contenteditable", "false");
            pill_container.find(".input").css("display", "none");
            pill_container.addClass("not-editable");
            pill_container.off("keydown", ".pill");
            pill_container.off("keydown", ".input");
            pill_container.off("click");
            pill_container.on("click", (e) => {
                e.stopPropagation();
            });
            pill_container.find(".pill").on("mouseenter", () => {
                pill_container.find(".pill").find(".exit").css("opacity", "0.5");
            });
        }
        update_membership(data.id);

        function is_user_group_changed() {
            const draft_group = get_pill_user_ids();
            const group_data = user_groups.get_user_group_from_id(data.id);
            const original_group = Array.from(group_data.members);
            const same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            const description = $(`#user-groups #${CSS.escape(data.id)} .description`)
                .text()
                .trim();
            const name = $(`#user-groups #${CSS.escape(data.id)} .name`)
                .text()
                .trim();
            const user_group_status = $(`#user-groups #${CSS.escape(data.id)} .user-group-status`);

            if (user_group_status.is(":visible")) {
                return false;
            }

            if (
                group_data.description === description &&
                group_data.name === name &&
                (!draft_group.length || same_groups)
            ) {
                return false;
            }
            return true;
        }

        function update_cancel_button() {
            if (!can_edit(data.id)) {
                return;
            }
            const cancel_button = $(`#user-groups #${CSS.escape(data.id)} .save-status.btn-danger`);
            const saved_button = $(`#user-groups #${CSS.escape(data.id)} .save-status.sea-green`);
            const save_instructions = $(`#user-groups #${CSS.escape(data.id)} .save-instructions`);

            if (is_user_group_changed() && !cancel_button.is(":visible")) {
                saved_button.fadeOut(0);
                cancel_button.css({display: "inline-block", opacity: "0"}).fadeTo(400, 1);
                save_instructions.css({display: "block", opacity: "0"}).fadeTo(400, 1);
            } else if (!is_user_group_changed() && cancel_button.is(":visible")) {
                cancel_button.fadeOut();
                save_instructions.fadeOut();
            }
        }

        function show_saved_button() {
            const cancel_button = $(`#user-groups #${CSS.escape(data.id)} .save-status.btn-danger`);
            const saved_button = $(`#user-groups #${CSS.escape(data.id)} .save-status.sea-green`);
            const save_instructions = $(`#user-groups #${CSS.escape(data.id)} .save-instructions`);
            if (!saved_button.is(":visible")) {
                cancel_button.fadeOut(0);
                save_instructions.fadeOut(0);
                saved_button
                    .css({display: "inline-block", opacity: "0"})
                    .fadeTo(400, 1)
                    .delay(2000)
                    .fadeTo(400, 0);
            }
        }

        function save_members() {
            const draft_group = get_pill_user_ids();
            const group_data = user_groups.get_user_group_from_id(data.id);
            const original_group = Array.from(group_data.members);
            const same_groups = _.isEqual(_.sortBy(draft_group), _.sortBy(original_group));
            if (!draft_group.length || same_groups) {
                return;
            }
            const added = _.difference(draft_group, original_group);
            const removed = _.difference(original_group, draft_group);
            channel.post({
                url: "/json/user_groups/" + data.id + "/members",
                data: {
                    add: JSON.stringify(added),
                    delete: JSON.stringify(removed),
                },
                success() {
                    setTimeout(show_saved_button, 200);
                },
            });
        }

        function save_name_desc() {
            const user_group_status = $(`#user-groups #${CSS.escape(data.id)} .user-group-status`);
            const group_data = user_groups.get_user_group_from_id(data.id);
            const description = $(`#user-groups #${CSS.escape(data.id)} .description`)
                .text()
                .trim();
            const name = $(`#user-groups #${CSS.escape(data.id)} .name`)
                .text()
                .trim();

            if (group_data.description === description && group_data.name === name) {
                return;
            }

            channel.patch({
                url: "/json/user_groups/" + data.id,
                data: {
                    name,
                    description,
                },
                success() {
                    user_group_status.hide();
                    setTimeout(show_saved_button, 200);
                },
                error(xhr) {
                    const errors = JSON.parse(xhr.responseText).msg;
                    xhr.responseText = JSON.stringify({msg: errors});
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, user_group_status);
                    update_cancel_button();
                    $(`#user-groups #${CSS.escape(data.id)} .name`).text(group_data.name);
                    $(`#user-groups #${CSS.escape(data.id)} .description`).text(
                        group_data.description,
                    );
                },
            });
        }

        function do_not_blur(except_class, event) {
            // Event generated from or inside the typeahead.
            if ($(event.relatedTarget).closest(".typeahead").length) {
                return true;
            }

            const blur_exceptions = _.without(
                [".pill-container", ".name", ".description", ".input", ".delete"],
                except_class,
            );
            if ($(event.relatedTarget).closest(`#user-groups #${CSS.escape(data.id)}`).length) {
                return blur_exceptions.some(
                    (class_name) => $(event.relatedTarget).closest(class_name).length,
                );
            }
            return false;
        }

        function auto_save(class_name, event) {
            if (!can_edit(data.id)) {
                return;
            }

            if (do_not_blur(class_name, event)) {
                return;
            }
            if (
                $(event.relatedTarget).closest(`#user-groups #${CSS.escape(data.id)}`) &&
                $(event.relatedTarget).closest(".save-status.btn-danger").length
            ) {
                reload();
                return;
            }
            save_name_desc();
            save_members();
        }

        $(`#user-groups #${CSS.escape(data.id)}`).on("blur", ".input", (event) => {
            auto_save(".input", event);
        });

        $(`#user-groups #${CSS.escape(data.id)}`).on("blur", ".name", (event) => {
            auto_save(".name", event);
        });
        $(`#user-groups #${CSS.escape(data.id)}`).on("input", ".name", () => {
            update_cancel_button();
        });

        $(`#user-groups #${CSS.escape(data.id)}`).on("blur", ".description", (event) => {
            auto_save(".description", event);
        });
        $(`#user-groups #${CSS.escape(data.id)}`).on("input", ".description", () => {
            update_cancel_button();
        });

        const input = pill_container.children(".input");
        if (can_edit(data.id)) {
            const opts = {update_func: update_cancel_button, user: true};
            pill_typeahead.set_up(input, pills, opts);
        }

        if (can_edit(data.id)) {
            pills.onPillRemove(() => {
                // onPillRemove is fired before the pill is removed from
                // the DOM.
                update_cancel_button();
                setTimeout(() => {
                    input.trigger("focus");
                }, 100);
            });
        }
    }
}

export function set_up() {
    meta.loaded = true;
    populate_user_groups();

    $(".organization form.admin-user-group-form")
        .off("submit")
        .on("submit", function (e) {
            e.preventDefault();
            e.stopPropagation();

            const user_group_status = $("#admin-user-group-status");

            const group = {
                members: JSON.stringify([people.my_current_user_id()]),
            };

            for (const obj of $(this).serializeArray()) {
                if (obj.value.trim() === "") {
                    continue;
                }
                group[obj.name] = obj.value;
            }

            channel.post({
                url: "/json/user_groups/create",
                data: group,
                success() {
                    user_group_status.hide();
                    ui_report.success(
                        $t_html({defaultMessage: "User group added!"}),
                        user_group_status,
                    );
                    $("form.admin-user-group-form input[type='text']").val("");
                },
                error(xhr) {
                    user_group_status.hide();
                    const errors = JSON.parse(xhr.responseText).msg;
                    xhr.responseText = JSON.stringify({msg: errors});
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, user_group_status);
                },
            });
        });

    $("#user-groups").on("click", ".delete", function () {
        const group_id = Number.parseInt($(this).parents(".user-group").attr("id"), 10);
        if (!can_edit(group_id)) {
            return;
        }
        const user_group = user_groups.get_user_group_from_id(group_id);
        const btn = $(this);

        function delete_user_group() {
            channel.del({
                url: "/json/user_groups/" + group_id,
                data: {
                    id: group_id,
                },
                error() {
                    btn.text($t({defaultMessage: "Failed!"}));
                },
            });
        }

        const html_body = render_confirm_delete_user({
            group_name: user_group.name,
        });

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete user group"}),
            html_body,
            on_click: delete_user_group,
        });
    });

    $("#user-groups").on("keypress", ".user-group h4 > span", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
        }
    });
}
