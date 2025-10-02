import Handlebars from "handlebars";
import $ from "jquery";

import render_add_alert_word from "../templates/settings/add_alert_word.hbs";
import render_alert_word_settings_item from "../templates/settings/alert_word_settings_item.hbs";

import * as alert_words from "./alert_words.ts";
import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import * as ui_report from "./ui_report.ts";

export let loaded = false;

export let rerender_alert_words_ui = (): void => {
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
};

export function rewire_rerender_alert_words_ui(value: typeof rerender_alert_words_ui): void {
    rerender_alert_words_ui = value;
}

const open_alert_word_status_banner = (alert_word: string, is_error: boolean): void => {
    const alert_word_status_banner: Banner = {
        intent: "danger",
        label: "",
        buttons: [],
        close_button: true,
        custom_classes: "alert-word-status-banner",
    };
    if (is_error) {
        alert_word_status_banner.label = new Handlebars.SafeString(
            $t_html(
                {defaultMessage: "Error removing alert word <b>{alert_word}</b>!"},
                {alert_word},
            ),
        );
        alert_word_status_banner.intent = "danger";
    } else {
        alert_word_status_banner.label = new Handlebars.SafeString(
            $t_html(
                {defaultMessage: "Alert word <b>{alert_word}</b> removed successfully!"},
                {alert_word},
            ),
        );
        alert_word_status_banner.intent = "success";
    }
    banners.open(alert_word_status_banner, $("#alert_word_status"));
};

function add_alert_word(): void {
    const alert_word = $<HTMLInputElement>("input#add-alert-word-name").val()!.trim();

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

function remove_alert_word(alert_word: string): void {
    const words_to_be_removed = [alert_word];
    void channel.del({
        url: "/json/users/me/alert_words",
        data: {alert_words: JSON.stringify(words_to_be_removed)},
        success() {
            open_alert_word_status_banner(alert_word, false);
        },
        error() {
            open_alert_word_status_banner(alert_word, true);
        },
    });
}

export function show_add_alert_word_modal(): void {
    const html_body = render_add_alert_word();

    function add_alert_word_post_render(): void {
        const $add_user_group_input_element = $<HTMLInputElement>("input#add-alert-word-name");
        const $add_user_group_submit_button = $("#add-alert-word .dialog_submit_button");
        $add_user_group_submit_button.prop("disabled", true);

        $add_user_group_input_element.on("input", () => {
            $add_user_group_submit_button.prop(
                "disabled",
                $add_user_group_input_element.val()!.trim() === "",
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

export function set_up_alert_words(): void {
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
}

export function reset(): void {
    loaded = false;
}
