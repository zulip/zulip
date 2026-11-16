import {$} from "jquery";
import assert from "minimalistic-assert";

import emoji_codes from "../../static/generated/emoji/emoji_codes.json";
import render_confirm_deactivate_custom_emoji from "../templates/confirm_dialog/confirm_deactivate_custom_emoji.hbs";
import emoji_settings_warning_modal from "../templates/confirm_dialog/confirm_emoji_settings_warning.hbs";
import render_add_emoji from "../templates/settings/add_emoji.hbs";
import render_admin_emoji_list from "../templates/settings/admin_emoji_list.hbs";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as emoji from "./emoji.ts";
import type {ServerEmoji} from "./emoji.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as people from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_data from "./settings_data.ts";
import {current_user} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
import * as upload_widget from "./upload_widget.ts";
import * as util from "./util.ts";

const meta = {
    loaded: false,
};

const MAX_EMOJI_CANVAS_DIMENSION = 512;

export type AspectRatioMode = "pad" | "crop";

let current_aspect_ratio_mode: AspectRatioMode = "pad";
let current_padded_file: File | null = null;
let is_non_square = false;

export function get_current_aspect_ratio_mode(): AspectRatioMode {
    return current_aspect_ratio_mode;
}

export function reset_custom_emoji_upload_state(): void {
    current_aspect_ratio_mode = "pad";
    current_padded_file = null;
    is_non_square = false;
}

export async function pad_image_to_square(image: HTMLImageElement, file: File): Promise<File> {
    if (typeof document === "undefined" || !("createElement" in document)) {
        return file;
    }

    const max_original_dim = Math.max(image.naturalWidth, image.naturalHeight);
    const canvas_size = Math.min(MAX_EMOJI_CANVAS_DIMENSION, max_original_dim);
    const scale = canvas_size / max_original_dim;
    const scaled_width = Math.round(image.naturalWidth * scale);
    const scaled_height = Math.round(image.naturalHeight * scale);
    const dx = Math.round((canvas_size - scaled_width) / 2);
    const dy = Math.round((canvas_size - scaled_height) / 2);

    const canvas = document.createElement("canvas");
    canvas.width = canvas_size;
    canvas.height = canvas_size;
    const ctx = canvas.getContext("2d");
    if (ctx !== null) {
        ctx.clearRect(0, 0, canvas_size, canvas_size);
        ctx.drawImage(image, dx, dy, scaled_width, scaled_height);
    }

    if (typeof canvas.toBlob !== "function") {
        return file;
    }

    return new Promise((resolve) => {
        canvas.toBlob((blob) => {
            if (blob === null) {
                resolve(file);
                return;
            }
            const new_name = file.name.replace(/\.[^.]+$/, "") + ".png";
            resolve(new File([blob], new_name, {type: "image/png"}));
        }, "image/png");
    });
}

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
    if (!settings_data.user_can_add_custom_emoji()) {
        $(".add-emoji-text").hide();
        $("#add-custom-emoji-button").hide();
        $("#emoji-settings .emoji-settings-tip-container").show();
        $(".org-settings-list li[data-section='emoji-settings'] .locked").show();
    } else {
        $(".add-emoji-text").show();
        $("#add-custom-emoji-button").show();
        $("#emoji-settings .emoji-settings-tip-container").hide();
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
            const author = item.author
                ? {
                      ...item.author,
                      is_active: people.is_person_active(item.author_id),
                      avatar_url: people.small_avatar_url_for_person(item.author),
                  }
                : "";
            return render_admin_emoji_list({
                emoji: {
                    name: item.name,
                    display_name: item.name.replaceAll("_", " "),
                    source_url: item.source_url,
                    author,
                    can_delete_emoji: can_delete_emoji(item),
                    is_overriding_default: is_default_emoji(item.name),
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
    const $toggle_button = $("#emoji_aspect_ratio_toggle_button");
    const $toggle_button_label = $("#emoji_aspect_ratio_toggle_button .action-button-label");
    const $upload_button = $("#emoji_upload_button");
    const $preview_text = $("#emoji_preview_text");
    const $preview_image = $("#emoji_preview_image");
    const $placeholder_icon = $("#emoji_placeholder_icon");

    $preview_image.hide();
    $toggle_button.hide();

    upload_widget.build_widget(
        get_file_input,
        $file_name_field,
        $input_error,
        $clear_button,
        $upload_button,
        $preview_text,
        $preview_image,
    );

    $toggle_button.on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        if (!is_non_square) {
            return;
        }

        if (current_aspect_ratio_mode === "pad") {
            current_aspect_ratio_mode = "crop";
            if ($toggle_button_label.length > 0) {
                $toggle_button_label.text($t({defaultMessage: "Pad to square"}));
            } else {
                $toggle_button.text($t({defaultMessage: "Pad to square"}));
            }
            $preview_image.removeClass("preview-pad").addClass("preview-crop");
        } else {
            current_aspect_ratio_mode = "pad";
            if ($toggle_button_label.length > 0) {
                $toggle_button_label.text($t({defaultMessage: "Crop to square"}));
            } else {
                $toggle_button.text($t({defaultMessage: "Crop to square"}));
            }
            $preview_image.removeClass("preview-crop").addClass("preview-pad");
        }
    });

    get_file_input().on("change", () => {
        reset_custom_emoji_upload_state();
        $toggle_button.hide();
        $preview_image.removeClass("preview-crop preview-pad");

        const input = util.the(get_file_input());
        const file = input.files?.[0];
        if (file === undefined) {
            return;
        }

        if (file.type === "image/gif") {
            return;
        }

        if (
            typeof Image === "undefined" ||
            typeof URL === "undefined" ||
            typeof URL.createObjectURL !== "function"
        ) {
            return;
        }

        const temp_url = URL.createObjectURL(file);
        const img = new Image();
        img.addEventListener("load", () => {
            if (typeof URL.revokeObjectURL === "function") {
                URL.revokeObjectURL(temp_url);
            }
            void (async () => {
                if (img.naturalWidth !== img.naturalHeight) {
                    is_non_square = true;
                    current_aspect_ratio_mode = "pad";
                    $toggle_button.show();
                    if ($toggle_button_label.length > 0) {
                        $toggle_button_label.text($t({defaultMessage: "Crop to square"}));
                    } else {
                        $toggle_button.text($t({defaultMessage: "Crop to square"}));
                    }
                    $preview_image.addClass("preview-pad");

                    current_padded_file = await pad_image_to_square(img, file);
                }
            })();
        });
        img.src = temp_url;
    });

    get_file_input().on("input", () => {
        $placeholder_icon.hide();
        $preview_image.show();
    });

    $preview_text.show();
    $clear_button.on("click", (e) => {
        e.stopPropagation();
        e.preventDefault();

        $("#add-custom-emoji-modal .dialog_submit_button").prop("disabled", true);

        reset_custom_emoji_upload_state();
        $toggle_button.hide();
        $preview_image.removeClass("preview-crop preview-pad");
        $preview_image.hide();
        $placeholder_icon.show();
        $preview_text.show();
    });
}

function show_modal(): void {
    const modal_content_html = render_add_emoji({});

    function add_custom_emoji(): void {
        dialog_widget.show_dialog_spinner();

        const $emoji_status = $("#dialog_error");
        const emoji: Record<string, string> = {};

        function submit_custom_emoji_request(formData: FormData): void {
            assert(emoji["name"] !== undefined);
            void channel.post({
                url: "/json/realm/emoji/" + encodeURIComponent(emoji["name"]),
                data: formData,
                cache: false,
                processData: false,
                contentType: false,
                success() {
                    dialog_widget.close();
                    reset_custom_emoji_upload_state();
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
        assert(emoji["name"] !== undefined);

        if (emoji["name"].trim() === "") {
            ui_report.client_error(
                $t_html({defaultMessage: "Failed: Emoji name is required."}),
                $emoji_status,
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }

        if (is_custom_emoji(emoji["name"])) {
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
        const files = util.the($<HTMLInputElement>("input#emoji_file_input")).files;
        assert(files !== null);
        for (const [i, file] of [...files].entries()) {
            if (i === 0 && current_aspect_ratio_mode === "pad" && current_padded_file !== null) {
                formData.append("file-" + i, current_padded_file);
            } else {
                formData.append("file-" + i, file);
            }
        }

        if (is_default_emoji(emoji["name"])) {
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
                const modal_content_html = emoji_settings_warning_modal({
                    emoji_name: emoji["name"],
                });
                confirm_dialog.launch({
                    modal_title_html: $t_html({defaultMessage: "Override default emoji?"}),
                    modal_content_html,
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
        modal_title_html: $t_html({defaultMessage: "Add a new emoji"}),
        modal_content_html,
        modal_submit_button_text: $t({defaultMessage: "Confirm"}),
        id: "add-custom-emoji-modal",
        form_id: "add-custom-emoji-form",
        loading_spinner: true,
        on_click: add_custom_emoji,
        post_render: add_custom_emoji_post_render,
        on_shown() {
            $("#emoji_name").trigger("focus");
        },
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
        const $button = $(this);
        const url =
            "/json/realm/emoji/" +
            encodeURIComponent($button.closest("tr").attr("data-emoji-name")!);
        const modal_content_html = render_confirm_deactivate_custom_emoji({});

        const opts = {
            success_continuation() {
                const $row = $button.parents("tr");
                $row.remove();
            },
        };

        confirm_dialog.launch({
            modal_title_html: $t_html({defaultMessage: "Deactivate custom emoji?"}),
            modal_content_html,
            id: "confirm_deactivate_custom_emoji_modal",
            on_click() {
                dialog_widget.submit_api_request(channel.del, url, {}, opts);
            },
            loading_spinner: true,
        });
    });
}
