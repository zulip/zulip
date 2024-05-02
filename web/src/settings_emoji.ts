import $ from "jquery";
import assert from "minimalistic-assert";

import emoji_codes from "../../static/generated/emoji/emoji_codes.json";
import render_confirm_deactivate_custom_emoji from "../templates/confirm_dialog/confirm_deactivate_custom_emoji.hbs";
import emoji_settings_warning_modal from "../templates/confirm_dialog/confirm_emoji_settings_warning.hbs";
import render_add_emoji from "../templates/settings/add_emoji.hbs";
import render_admin_emoji_list from "../templates/settings/admin_emoji_list.hbs";
import render_settings_emoji_settings_tip from "../templates/settings/emoji_settings_tip.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import * as emoji from "./emoji";
import type {ServerEmoji} from "./emoji";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as ui_report from "./ui_report";
import * as upload_widget from "./upload_widget";
import * as util from "./util";

const meta = {
    loaded: false,
};

function can_delete_emoji(emoji: ServerEmoji): boolean {
    if (current_user.is_admin) {
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

export function update_custom_emoji_ui(): void {
    const rendered_tip = render_settings_emoji_settings_tip({
        realm_add_custom_emoji_policy: realm.realm_add_custom_emoji_policy,
        policy_values: settings_config.common_policy_values,
    });
    $("#emoji-settings").find(".emoji-settings-tip-container").html(rendered_tip);
    if (!settings_data.user_can_add_custom_emoji()) {
        $(".add-emoji-text").hide();
        $("#add-custom-emoji-button").hide();
        $("#emoji-settings .emoji-settings-tip-container").show();
        $(".org-settings-list li[data-section='emoji-settings'] .locked").show();
    } else {
        $(".add-emoji-text").show();
        $("#add-custom-emoji-button").show();
        if (current_user.is_admin) {
            $("#emoji-settings .emoji-settings-tip-container").show();
        } else {
            $("#emoji-settings .emoji-settings-tip-container").hide();
        }
        $(".org-settings-list li[data-section='emoji-settings'] .locked").hide();
    }

    populate_emoji();
}

export function reset(): void {
    meta.loaded = false;
}

function sort_author_full_name(a: ServerEmoji, b: ServerEmoji): number {
    const author_a = a.author?.full_name;
    const author_b = b.author?.full_name;

    if (author_a === author_b) {
        return 0;
    }

    if (author_a && author_b) {
        return util.strcmp(author_a, author_b);
    }

    // If one of the author is null, then we put the null author at the end.
    return author_a ? -1 : 1;
}

function is_default_emoji(emoji_name: string): boolean {
    // Spaces are replaced with `_` to match how the emoji name will
    // actually be stored in the backend.
    return emoji_codes.names.includes(emoji_name.replaceAll(" ", "_"));
}

function is_custom_emoji(emoji_name: string): boolean {
    const emoji_data = emoji.get_server_realm_emoji_data();
    for (const emoji of Object.values(emoji_data)) {
        if (emoji.name === emoji_name && !emoji.deactivated) {
            return true;
        }
    }
    return false;
}

export function populate_emoji(): void {
    if (!meta.loaded) {
        return;
    }

    const emoji_data = emoji.get_server_realm_emoji_data();
    const active_emoji_data = Object.values(emoji_data).filter((emoji) => !emoji.deactivated);

    for (const emoji of active_emoji_data) {
        // Add people.js data for the user here.
        if (emoji.author_id !== null) {
            emoji.author = people.get_user_by_id_assert_valid(emoji.author_id);
        } else {
            emoji.author = null;
        }
    }

    const $emoji_table = $("#admin_emoji_table").expectOne();
    ListWidget.create<ServerEmoji>($emoji_table, active_emoji_data, {
        name: "emoji_list",
        get_item: ListWidget.default_get_item,
        modifier_html(item) {
            return render_admin_emoji_list({
                emoji: {
                    name: item.name,
                    display_name: item.name.replaceAll("_", " "),
                    source_url: item.source_url,
                    author: item.author ?? "",
                    can_delete_emoji: can_delete_emoji(item),
                },
            });
        },
        filter: {
            $element: $emoji_table
                .closest(".settings-section")
                .find<HTMLInputElement>("input.search"),
            predicate(item, value) {
                return item.name.toLowerCase().includes(value);
            },
            onupdate() {
                scroll_util.reset_scrollbar($emoji_table);
            },
        },
        $parent_container: $("#emoji-settings").expectOne(),
        sort_fields: {
            author_full_name: sort_author_full_name,
            ...ListWidget.generic_sort_functions("alphabetic", ["name"]),
        },
        init_sort: "name_alphabetic",
        $simplebar_container: $("#emoji-settings .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_emoji_loading_indicator"));
}

export function add_custom_emoji_post_render(): void {
    $("#add-custom-emoji-modal .dialog_submit_button").prop("disabled", true);

    $("#add-custom-emoji-form").on("input", "input", () => {
        $("#add-custom-emoji-modal .dialog_submit_button").prop(
            "disabled",
            $("#emoji_name").val() === "" || $("#emoji_file_input").val() === "",
        );
    });

    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $("#emoji_file_input");
    };

    const $file_name_field = $("#emoji-file-name");
    const $input_error = $("#emoji_file_input_error");
    const $clear_button = $("#emoji_image_clear_button");
    const $upload_button = $("#emoji_upload_button");
    const $preview_text = $("#emoji_preview_text");
    const $preview_image = $("#emoji_preview_image");
    const $placeholder_icon = $("#emoji_placeholder_icon");

    $preview_image.hide();

    upload_widget.build_widget(
        get_file_input,
        $file_name_field,
        $input_error,
        $clear_button,
        $upload_button,
        $preview_text,
        $preview_image,
    );

    get_file_input().on("input", () => {
        $placeholder_icon.hide();
        $preview_image.show();
    });

    $preview_text.show();
    $clear_button.on("click", (e) => {
        e.stopPropagation();
        e.preventDefault();

        $("#add-custom-emoji-modal .dialog_submit_button").prop("disabled", true);

        $preview_image.hide();
        $placeholder_icon.show();
        $preview_text.show();
    });
}

function show_modal(): void {
    const html_body = render_add_emoji({});

    function add_custom_emoji(): void {
        dialog_widget.show_dialog_spinner();

        const $emoji_status = $("#dialog_error");
        const emoji: Record<string, string> = {};

        function submit_custom_emoji_request(formData: FormData): void {
            void channel.post({
                url: "/json/realm/emoji/" + encodeURIComponent(emoji.name),
                data: formData,
                cache: false,
                processData: false,
                contentType: false,
                success() {
                    dialog_widget.close();
                },
                error(xhr) {
                    $("#dialog_error").hide();
                    dialog_widget.hide_dialog_spinner();
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $emoji_status);
                },
            });
        }

        for (const obj of $("#add-custom-emoji-form").serializeArray()) {
            emoji[obj.name] = obj.value;
        }

        if (emoji.name.trim() === "") {
            ui_report.client_error(
                $t_html({defaultMessage: "Failed: Emoji name is required."}),
                $emoji_status,
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }

        if (is_custom_emoji(emoji.name)) {
            ui_report.client_error(
                $t_html({
                    defaultMessage: "Failed: A custom emoji with this name already exists.",
                }),
                $emoji_status,
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }

        const formData = new FormData();
        const files = $<HTMLInputElement>("input#emoji_file_input")[0].files;
        assert(files !== null);
        for (const [i, file] of [...files].entries()) {
            formData.append("file-" + i, file);
        }

        if (is_default_emoji(emoji.name)) {
            if (!current_user.is_admin) {
                ui_report.client_error(
                    $t_html({
                        defaultMessage:
                            "Failed: There is a default emoji with this name. Only administrators can override default emoji.",
                    }),
                    $emoji_status,
                );
                dialog_widget.hide_dialog_spinner();
                return;
            }

            dialog_widget.close(() => {
                const html_body = emoji_settings_warning_modal({
                    emoji_name: emoji.name,
                });
                confirm_dialog.launch({
                    html_heading: $t_html({defaultMessage: "Override default emoji?"}),
                    html_body,
                    on_click() {
                        submit_custom_emoji_request(formData);
                    },
                });
            });
        } else {
            submit_custom_emoji_request(formData);
        }
    }
    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Add a new emoji"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
        id: "add-custom-emoji-modal",
        form_id: "add-custom-emoji-form",
        loading_spinner: true,
        on_click: add_custom_emoji,
        post_render: add_custom_emoji_post_render,
    });
}

export function set_up(): void {
    meta.loaded = true;

    $("#add-custom-emoji-button").on("click", show_modal);

    loading.make_indicator($("#admin_page_emoji_loading_indicator"));

    // Populate emoji table
    populate_emoji();

    $(".admin_emoji_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $btn = $(this);
        const url = "/json/realm/emoji/" + encodeURIComponent($btn.attr("data-emoji-name")!);
        const html_body = render_confirm_deactivate_custom_emoji({});

        const opts = {
            success_continuation() {
                const $row = $btn.parents("tr");
                $row.remove();
            },
        };

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Deactivate custom emoji?"}),
            html_body,
            id: "confirm_deactivate_custom_emoji_modal",
            on_click() {
                dialog_widget.submit_api_request(channel.del, url, {}, opts);
            },
            loading_spinner: true,
        });
    });
}
