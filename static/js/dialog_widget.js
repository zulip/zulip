import $ from "jquery";
import Micromodal from "micromodal";

import render_dialog_widget from "../templates/dialog_widget.hbs";

import * as blueslip from "./blueslip";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as overlays from "./overlays";

/*
 *  Look for confirm_dialog in settings_user_groups
 *  to see an example of how to use this widget.  It's
 *  pretty simple to use!
 *
 *  Some things to note:
 *      1) We create DOM on the fly, and we remove
 *         the DOM once it's closed.
 *
 *      2) We attach the DOM for the modal to the body element
 *         to avoid interference from other elements.
 *
 *      3) For settings, we have a click handler in settings.js
 *         that will close the dialog via overlays.close_active_modal.
 *
 *      4) We assume that since this is a modal, you will
 *         only ever have one confirm dialog active at any
 *         time.
 *
 *      5) If a modal wants a loading spinner, it should pass loading_spinner: true.
 *         This will show a loading spinner when the yes button is clicked.
 *         The caller is responsible for calling hide_confirm_dialog_spinner()
 *         to hide the spinner in both success and error handlers.
 *
 *      6) If loading_spinner is used, don't hide it on `success`. This modal has a fade out
 *         animation. This causes the `Confirm` button to be shown for a split second if the
 *         spinner is hidden.
 *         Just close the modal. This will remove the whole modal from the DOM without
 *         needing to remove the spinner.
 *
 *      7) If a caller needs to run code after the modal body is added
 *          to DOM, it can do so by passing a post_render hook.
 */

export function hide_dialog_spinner() {
    $(".dialog_submit_button span").show();
    $("#dialog_widget_modal .modal__btn").prop("disabled", false);

    const spinner = $("#dialog_widget_modal .modal__spinner");
    loading.destroy_indicator(spinner);
}

export function show_dialog_spinner() {
    $(".dialog_submit_button span").hide();
    // Disable both the buttons.
    $("#dialog_widget_modal .modal__btn").prop("disabled", true);

    const spinner = $("#dialog_widget_modal .modal__spinner");
    loading.make_indicator(spinner);
}

export function close_modal() {
    Micromodal.close("dialog_widget_modal");
}

export function launch(conf) {
    const mandatory_fields = [
        // The html_ fields should be safe HTML. If callers
        // interpolate user data into strings, they should use
        // templates.
        "html_heading",
        "html_body",
        "on_click",
    ];

    // Optional parameters:
    // * html_submit_button: Submit button text.
    // * close_on_submit: Whether to close modal on clicking submit.
    // * focus_submit_on_open: Whether to focus submit button on open.
    // * help_link: A help link in the heading area.
    // * id: Custom id to the container element to modify styles.
    // * single_footer_button: If true, don't include the "Cancel" button.

    for (const f of mandatory_fields) {
        if (conf[f] === undefined) {
            blueslip.error("programmer omitted " + f);
        }
    }

    // Close any existing modals--on settings screens you can
    // have multiple buttons that need confirmation.
    if (overlays.is_modal_open()) {
        close_modal();
    }

    const html_submit_button = conf.html_submit_button || $t_html({defaultMessage: "Save changes"});
    const html = render_dialog_widget({
        heading_text: conf.html_heading,
        link: conf.help_link,
        html_submit_button,
        html_body: conf.html_body,
        id: conf.id,
        single_footer_button: conf.single_footer_button,
    });
    const dialog = $(html);
    $("body").append(dialog);

    if (conf.post_render !== undefined) {
        conf.post_render();
    }

    const submit_button = dialog.find(".dialog_submit_button");
    // Set up handlers.
    submit_button.on("click", (e) => {
        if (conf.loading_spinner) {
            show_dialog_spinner();
        } else if (conf.close_on_submit) {
            close_modal();
        }
        $("#dialog_error").empty();
        conf.on_click(e);
    });

    overlays.open_modal("dialog_widget_modal", {
        autoremove: true,
        micromodal: true,
        micromodal_opts: {
            onShow: () => {
                if (conf.focus_submit_on_open) {
                    submit_button.trigger("focus");
                }
            },
        },
    });
}
