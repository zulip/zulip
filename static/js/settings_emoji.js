import $ from "jquery";

import emoji_codes from "../generated/emoji/emoji_codes.json";
import * as emoji from "../shared/js/emoji";
import emoji_settings_warning_modal from "../templates/confirm_dialog/confirm_emoji_settings_warning.hbs";
import render_admin_emoji_list from "../templates/settings/admin_emoji_list.hbs";
import render_settings_emoji_settings_tip from "../templates/settings/emoji_settings_tip.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import * as upload_widget from "./upload_widget";

const meta = {
    loaded: false,
};

function can_delete_emoji(emoji) {
    if (page_params.is_admin) {
        return true;
    }
    if (emoji.author_id === null) {
        // If we don't have the author information then only admin is allowed to disable that emoji.
        return false;
    }
    if (people.is_my_user_id(emoji.author_id)) {
        return true;
    }
    return false;
}

export function update_custom_emoji_ui() {
    const rendered_tip = render_settings_emoji_settings_tip({
        realm_add_custom_emoji_policy: page_params.realm_add_custom_emoji_policy,
        policy_values: settings_config.common_policy_values,
    });
    $("#emoji-settings").find(".emoji-settings-tip-container").html(rendered_tip);
    if (!settings_data.user_can_add_custom_emoji()) {
        $(".add-emoji-text").hide();
        $(".admin-emoji-form").hide();
    } else {
        $(".add-emoji-text").show();
        $(".admin-emoji-form").show();
    }

    populate_emoji();
}

export function reset() {
    meta.loaded = false;
}

function sort_author_full_name(a, b) {
    if (a.author.full_name > b.author.full_name) {
        return 1;
    } else if (a.author.full_name === b.author.full_name) {
        return 0;
    }
    return -1;
}

function is_default_emoji(emoji_name) {
    return emoji_codes.names.includes(emoji_name);
}

function is_custom_emoji(emoji_name) {
    const emoji_data = emoji.get_server_realm_emoji_data();
    for (const emoji of Object.values(emoji_data)) {
        if (emoji.name === emoji_name && !emoji.deactivated) {
            return true;
        }
    }
    return false;
}

export function populate_emoji() {
    if (!meta.loaded) {
        return;
    }

    const emoji_data = emoji.get_server_realm_emoji_data();

    for (const emoji of Object.values(emoji_data)) {
        // Add people.js data for the user here.
        if (emoji.author_id !== null) {
            emoji.author = people.get_by_user_id(emoji.author_id);
        } else {
            emoji.author = null;
        }
    }

    const emoji_table = $("#admin_emoji_table").expectOne();
    ListWidget.create(emoji_table, Object.values(emoji_data), {
        name: "emoji_list",
        modifier(item) {
            if (item.deactivated !== true) {
                return render_admin_emoji_list({
                    emoji: {
                        name: item.name,
                        display_name: item.name.replace(/_/g, " "),
                        source_url: item.source_url,
                        author: item.author || "",
                        can_delete_emoji: can_delete_emoji(item),
                    },
                });
            }
            return "";
        },
        filter: {
            element: emoji_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return item.name.toLowerCase().includes(value);
            },
            onupdate() {
                ui.reset_scrollbar(emoji_table);
            },
        },
        parent_container: $("#emoji-settings").expectOne(),
        sort_fields: {
            author_full_name: sort_author_full_name,
        },
        init_sort: ["alphabetic", "name"],
        simplebar_container: $("#emoji-settings .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_emoji_loading_indicator"));
}

export function build_emoji_upload_widget() {
    const get_file_input = function () {
        return $("#emoji_file_input");
    };

    const file_name_field = $("#emoji-file-name");
    const input_error = $("#emoji_file_input_error");
    const clear_button = $("#emoji_image_clear_button");
    const upload_button = $("#emoji_upload_button");
    const preview_text = $("#emoji_preview_text");
    const preview_image = $("#emoji_preview_image");

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button,
        preview_text,
        preview_image,
    );
}

export function set_up() {
    meta.loaded = true;

    loading.make_indicator($("#admin_page_emoji_loading_indicator"));

    // Populate emoji table
    populate_emoji();

    $(".admin_emoji_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = $(this);

        channel.del({
            url: "/json/realm/emoji/" + encodeURIComponent(btn.attr("data-emoji-name")),
            error(xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            success() {
                const row = btn.parents("tr");
                row.remove();
            },
        });
    });

    const emoji_widget = build_emoji_upload_widget();

    $(".organization form.admin-emoji-form")
        .off("submit")
        .on("submit", function (e) {
            e.preventDefault();
            e.stopPropagation();
            const emoji_status = $("#admin-emoji-status");
            const emoji = {};

            function submit_custom_emoji_request() {
                $("#admin_emoji_submit").prop("disabled", true);
                const formData = new FormData();
                for (const [i, file] of Array.prototype.entries.call(
                    $("#emoji_file_input")[0].files,
                )) {
                    formData.append("file-" + i, file);
                }

                channel.post({
                    url: "/json/realm/emoji/" + encodeURIComponent(emoji.name),
                    data: formData,
                    cache: false,
                    processData: false,
                    contentType: false,
                    success() {
                        $("#admin-emoji-status").hide();
                        ui_report.success(
                            $t_html({defaultMessage: "Custom emoji added!"}),
                            emoji_status,
                        );
                        $("form.admin-emoji-form input[type='text']").val("");
                        $("#admin_emoji_submit").prop("disabled", false);
                        emoji_widget.clear();
                    },
                    error(xhr) {
                        $("#admin-emoji-status").hide();
                        const errors = JSON.parse(xhr.responseText).msg;
                        xhr.responseText = JSON.stringify({msg: errors});
                        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, emoji_status);
                        $("#admin_emoji_submit").prop("disabled", false);
                    },
                });
            }

            for (const obj of $(this).serializeArray()) {
                emoji[obj.name] = obj.value;
            }

            if (emoji.name.trim() === "") {
                ui_report.client_error(
                    $t_html({defaultMessage: "Failed: Emoji name is required."}),
                    emoji_status,
                );
                return;
            }

            if (is_custom_emoji(emoji.name)) {
                ui_report.client_error(
                    $t_html({
                        defaultMessage: "Failed: A custom emoji with this name already exists.",
                    }),
                    emoji_status,
                );
                return;
            }

            if (is_default_emoji(emoji.name)) {
                const html_body = emoji_settings_warning_modal({
                    emoji_name: emoji.name,
                });

                confirm_dialog.launch({
                    html_heading: $t_html({defaultMessage: "Override built-in emoji?"}),
                    html_body,
                    on_click: submit_custom_emoji_request,
                });
            } else {
                submit_custom_emoji_request();
            }
        });
}
