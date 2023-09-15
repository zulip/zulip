import $ from "jquery";

import render_add_alert_word from "../templates/settings/add_alert_word.hbs";
import render_alert_word_settings_item from "../templates/settings/alert_word_settings_item.hbs";

import * as alert_words from "./alert_words";
import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as ui_report from "./ui_report";

export let loaded = false;

export function rerender_alert_words_ui() {
    if (!loaded) {
        return;
    }

    const words = alert_words.get_word_list();
    words.sort();
    const $word_list = $("#alert-words-table");

    ListWidget.create($word_list, words, {
        name: "alert-words-list",
        get_item: ListWidget.default_get_item,
        modifier_html(alert_word) {
            return render_alert_word_settings_item({alert_word});
        },
        $parent_container: $("#alert-word-settings"),
        $simplebar_container: $("#alert-word-settings .progressive-table-wrapper"),
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", ["word"]),
        },
    });
}

function update_alert_word_status(status_text, is_error) {
    const $alert_word_status = $("#alert_word_status");
    if (is_error) {
        $alert_word_status.removeClass("alert-success").addClass("alert-danger");
    } else {
        $alert_word_status.removeClass("alert-danger").addClass("alert-success");
    }
    $alert_word_status.find(".alert_word_status_text").text(status_text);
    $alert_word_status.show();
}

function add_alert_word() {
    const alert_word = $("#add-alert-word-name").val().trim();

    if (alert_words.has_alert_word(alert_word)) {
        ui_report.client_error(
            $t({defaultMessage: "Alert word already exists!"}),
            $("#dialog_error"),
        );
        dialog_widget.hide_dialog_spinner();
        return;
    }

    const words_to_be_added = [alert_word];

    const data = {alert_words: JSON.stringify(words_to_be_added)};
    dialog_widget.submit_api_request(channel.post, "/json/users/me/alert_words", data);
}

function remove_alert_word(alert_word) {
    const words_to_be_removed = [alert_word];
    channel.del({
        url: "/json/users/me/alert_words",
        data: {alert_words: JSON.stringify(words_to_be_removed)},
        success() {
            update_alert_word_status(
                $t(
                    {defaultMessage: `Alert word "{alert_word}" removed successfully!`},
                    {alert_word},
                ),
                false,
            );
        },
        error() {
            update_alert_word_status($t({defaultMessage: "Error removing alert word!"}), true);
        },
    });
}

export function show_add_alert_word_modal() {
    const html_body = render_add_alert_word();

    function add_alert_word_post_render() {
        const $add_user_group_input_element = $("#add-alert-word-name");
        const $add_user_group_submit_button = $("#add-alert-word .dialog_submit_button");
        $add_user_group_submit_button.prop("disabled", true);

        $add_user_group_input_element.on("input", () => {
            $add_user_group_submit_button.prop(
                "disabled",
                $add_user_group_input_element.val().trim() === "",
            );
        });
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Add a new alert word"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Add"}),
        help_link: "/help/dm-mention-alert-notifications#alert-words",
        form_id: "add-alert-word-form",
        id: "add-alert-word",
        loading_spinner: true,
        on_click: add_alert_word,
        on_shown: () => $("#add-alert-word-name").trigger("focus"),
        post_render: add_alert_word_post_render,
    });
}

export function set_up_alert_words() {
    // The settings page must be rendered before this function gets called.
    loaded = true;
    rerender_alert_words_ui();

    $("#open-add-alert-word-modal").on("click", () => {
        show_add_alert_word_modal();
    });

    $("#alert-words-table").on("click", ".remove-alert-word", (event) => {
        const word = $(event.currentTarget).parents("tr").find(".value").text().trim();
        remove_alert_word(word);
    });

    $("#alert-word-settings").on("click", ".close-alert-word-status", (event) => {
        event.preventDefault();
        const $alert = $(event.currentTarget).parents(".alert");
        $alert.hide();
    });
}

export function reset() {
    loaded = false;
}
