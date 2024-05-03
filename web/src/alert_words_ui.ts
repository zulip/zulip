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

export function rerender_watched_phrases_ui(): void {
    if (!loaded) {
        return;
    }

    const watched_phrase_data = alert_words.get_watched_phrase_data();
    watched_phrase_data.sort((a, b) => a.watched_phrase.length - b.watched_phrase.length);
    const $word_list = $("#watched-phrases-table");

    ListWidget.create($word_list, watched_phrase_data, {
        name: "watched-phrases-list",
        get_item: ListWidget.default_get_item,
        modifier_html(watched_phrase) {
            return render_alert_word_settings_item({watched_phrase});
        },
        $parent_container: $("#watched-phrase-settings"),
        $simplebar_container: $("#watched-phrase-settings .progressive-table-wrapper"),
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", ["watched_phrase"]),
        },
    });
}

function update_watched_phrase_status(status_text: string, is_error: boolean): void {
    const $watched_phrase_status = $("#watched_phrase_status");
    if (is_error) {
        $watched_phrase_status.removeClass("alert-success").addClass("alert-danger");
    } else {
        $watched_phrase_status.removeClass("alert-danger").addClass("alert-success");
    }
    $watched_phrase_status.find(".watched_phrase_status_text").text(status_text);
    $watched_phrase_status.show();
}

function add_watched_phrase(): void {
    const watched_phrase = $<HTMLInputElement>("input#add-watched-phrase-name").val()!.trim();

    if (alert_words.has_watched_phrase(watched_phrase)) {
        ui_report.client_error(
            $t({defaultMessage: "Watched phrase already exists!"}),
            $("#dialog_error"),
        );
        dialog_widget.hide_dialog_spinner();
        return;
    }

    const watched_phrases_to_be_added = [{watched_phrase}];

    const data = {watched_phrases: JSON.stringify(watched_phrases_to_be_added)};
    dialog_widget.submit_api_request(channel.post, "/json/users/me/watched_phrases", data);
}

function remove_watched_phrase(watched_phrase: string): void {
    const words_to_be_removed = [watched_phrase];
    void channel.del({
        url: "/json/users/me/watched_phrases",
        data: {watched_phrases: JSON.stringify(words_to_be_removed)},
        success() {
            update_watched_phrase_status(
                $t(
                    {defaultMessage: `Watched phrase "{watched_phrase}" removed successfully!`},
                    {watched_phrase},
                ),
                false,
            );
        },
        error() {
            update_watched_phrase_status(
                $t({defaultMessage: "Error removing watched phrase!"}),
                true,
            );
        },
    });
}

export function show_add_watched_phrase_modal(): void {
    const html_body = render_add_alert_word();

    function add_watched_phrase_post_render(): void {
        const $add_user_group_input_element = $<HTMLInputElement>("input#add-watched-phrase-name");
        const $add_user_group_submit_button = $("#add-watched-phrase .dialog_submit_button");
        $add_user_group_submit_button.prop("disabled", true);

        $add_user_group_input_element.on("input", () => {
            $add_user_group_submit_button.prop(
                "disabled",
                $add_user_group_input_element.val()!.trim() === "",
            );
        });
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Add a new watched phrase"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Add"}),
        help_link: "/help/dm-mention-alert-notifications#alert-words",
        form_id: "add-watched-phrase-form",
        id: "add-watched-phrase",
        loading_spinner: true,
        on_click: add_watched_phrase,
        on_shown: () => $("#add-watched-phrase-name").trigger("focus"),
        post_render: add_watched_phrase_post_render,
    });
}

export function set_up_watched_phrases(): void {
    // The settings page must be rendered before this function gets called.
    loaded = true;
    rerender_watched_phrases_ui();

    $("#open-add-watched-phrase-modal").on("click", () => {
        show_add_watched_phrase_modal();
    });

    $("#watched-phrases-table").on("click", ".remove-watched-phrase", (event) => {
        const word = $(event.currentTarget).parents("tr").find(".value").text().trim();
        remove_watched_phrase(word);
    });

    $("#watched-phrase-settings").on("click", ".close-watched-phrase-status", (event) => {
        event.preventDefault();
        const $alert = $(event.currentTarget).parents(".alert");
        $alert.hide();
    });
}

export function reset(): void {
    loaded = false;
}
