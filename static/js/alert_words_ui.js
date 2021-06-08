import $ from "jquery";

import render_alert_word_settings_item from "../templates/settings/alert_word_settings_item.hbs";

import * as alert_words from "./alert_words";
import * as channel from "./channel";
import {$t} from "./i18n";

export function render_alert_words_ui() {
    const words = alert_words.get_word_list();
    words.sort();
    const word_list = $("#alert_words_list");

    word_list.find(".alert-word-item").remove();

    for (const alert_word of words) {
        const rendered_alert_word = render_alert_word_settings_item({
            word: alert_word,
        });
        word_list.append(rendered_alert_word);
    }

    // Focus new alert word name text box.
    $("#create_alert_word_name").trigger("focus");
}

function update_alert_word_status(status_text, is_error) {
    const alert_word_status = $("#alert_word_status");
    if (is_error) {
        alert_word_status.removeClass("alert-success").addClass("alert-danger");
    } else {
        alert_word_status.removeClass("alert-danger").addClass("alert-success");
    }
    alert_word_status.find(".alert_word_status_text").text(status_text);
    alert_word_status.show();
}

function add_alert_word(alert_word) {
    alert_word = alert_word.trim();
    if (alert_word === "") {
        update_alert_word_status($t({defaultMessage: "Alert word can't be empty!"}), true);
        return;
    } else if (alert_words.has_alert_word(alert_word)) {
        update_alert_word_status($t({defaultMessage: "Alert word already exists!"}), true);
        return;
    }

    const words_to_be_added = [alert_word];

    channel.post({
        url: "/json/users/me/alert_words",
        data: {alert_words: JSON.stringify(words_to_be_added)},
        success() {
            const message = $t(
                {defaultMessage: 'Alert word "{word}" added successfully!'},
                {word: words_to_be_added[0]},
            );
            update_alert_word_status(message, false);
            $("#create_alert_word_name").val("");
        },
        error() {
            update_alert_word_status($t({defaultMessage: "Error adding alert word!"}), true);
        },
    });
}

function remove_alert_word(alert_word) {
    const words_to_be_removed = [alert_word];
    channel.del({
        url: "/json/users/me/alert_words",
        data: {alert_words: JSON.stringify(words_to_be_removed)},
        success() {
            update_alert_word_status(
                $t({defaultMessage: "Alert word removed successfully!"}),
                false,
            );
        },
        error() {
            update_alert_word_status($t({defaultMessage: "Error removing alert word!"}), true);
        },
    });
}

export function set_up_alert_words() {
    // The settings page must be rendered before this function gets called.

    render_alert_words_ui();

    $("#create_alert_word_form").on("click", "#create_alert_word_button", () => {
        const word = $("#create_alert_word_name").val();
        add_alert_word(word);
    });

    $("#alert_words_list").on("click", ".remove-alert-word", (event) => {
        const word = $(event.currentTarget).parents("tr").find(".value").text().trim();
        remove_alert_word(word);
    });

    $("#create_alert_word_form").on("keypress", "#create_alert_word_name", (event) => {
        // Handle Enter as "add".
        if (event.key === "Enter") {
            event.preventDefault();
            const word = $(event.target).val();
            add_alert_word(word);
        }
    });

    $("#alert-word-settings").on("click", ".close-alert-word-status", (event) => {
        event.preventDefault();
        const alert = $(event.currentTarget).parents(".alert");
        alert.hide();
    });
}
