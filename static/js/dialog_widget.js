import $ from "jquery";

import render_dialog_widget from "../templates/dialog_widget.hbs";
import render_dialog_heading from "../templates/dialog_widget_heading.hbs";

import * as blueslip from "./blueslip";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as overlays from "./overlays";
import * as settings_data from "./settings_data";

/*
    Look for dialog_widget in settings_users
    to see an example of how to use this widget.  It's
    pretty simple to use!

    Some things to note:

        1) We create DOM on the fly, and we remove
           the DOM once it's closed.

        2) We attach the DOM for the modal to conf.parent,
           and this temporary DOM location will influence
           how styles work.

        3) The cancel button is driven by bootstrap.js.

        4) For settings, we have a click handler in settings.js
           that will close the dialog via overlays.close_active_modal.

        5) We assume that since this is a modal, you will
           only ever have one dialog active at any
           time.

        6) If a modal wants a loading spinner, it should pass loading_spinner: true.
           This will show a loading spinner when the yes button is clicked.
           The caller is responsible for calling hide_dialog_spinner()
           to hide the spinner in both success and error handlers.

        7) If a caller needs to run code after the modal body is added
           to DOM, it can do so by passing a post_render hook.
*/

export function hide_dialog_spinner() {
    $(".dialog_submit_button .loader").hide();
    $(".dialog_submit_button span").show();
    $(".dialog_submit_button").prop("disabled", false);
    $("#dialog_widget_modal .close-modal-btn").prop("disabled", false);
}

export function show_dialog_spinner() {
    const using_dark_theme = settings_data.using_dark_theme();
    loading.show_button_spinner($(".dialog_submit_button .loader"), using_dark_theme);
    $(".dialog_submit_button span").hide();
    $(".dialog_submit_button").prop("disabled", true);
    $("#dialog_widget_modal .close-modal-btn").prop("disabled", true);
}

export function launch(conf) {
    const mandatory_fields = [
        // The html_ fields should be safe HTML. If callers
        // interpolate user data into strings, they should use
        // templates.
        "html_heading",
        "html_body",
        "on_click",
        "parent",
    ];

    // Optional parameters:
    // * html_submit_button: Submit button text.
    // * close_on_submit: Whether to close modal on clicking submit.
    // * focus_submit_on_open: Whether to focus submit button on open.
    // * danger_submit_button: Whether to use danger button styling for submit button.
    // * help_link: A help link in the heading area.

    for (const f of mandatory_fields) {
        if (conf[f] === undefined) {
            blueslip.error("programmer omitted " + f);
        }
    }

    // Close any existing modals--on settings screens you can
    // have multiple buttons that need confirmation.
    if (overlays.is_modal_open()) {
        overlays.close_modal("#dialog_widget_modal");
    }

    const html_submit_button = conf.html_submit_button || $t_html({defaultMessage: "Save changes"});
    const html_dialog_heading = render_dialog_heading({
        heading_text: conf.html_heading,
        link: conf.help_link,
    });
    const html = render_dialog_widget({
        fade: conf.fade,
        html_submit_button,
        html_dialog_heading,
        html_body: conf.html_body,
        danger_submit_button: conf.danger_submit_button,
    });
    const dialog = $(html);
    conf.parent.append(dialog);

    if (conf.post_render !== undefined) {
        conf.post_render();
    }

    const submit_button = dialog.find(".dialog_submit_button");
    // Set up handlers.
    submit_button.on("click", () => {
        if (conf.loading_spinner) {
            show_dialog_spinner();
        } else if (conf.close_on_submit) {
            overlays.close_modal("#dialog_widget_modal");
        }
        $("#dialog_error").empty();
        conf.on_click();
    });

    dialog.on("hidden.bs.modal", () => {
        dialog.remove();
    });

    if (conf.focus_submit_on_open) {
        conf.parent.on("shown.bs.modal", () => {
            submit_button.trigger("focus");
        });
    }

    // Open the modal
    overlays.open_modal("#dialog_widget_modal");
}
