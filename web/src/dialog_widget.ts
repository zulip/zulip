import $ from "jquery";
import _ from "lodash";

import render_dialog_widget from "../templates/dialog_widget.hbs";

import type {AjaxRequestHandler} from "./channel";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as modals from "./modals";
import * as ui_report from "./ui_report";

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
 *         that will close the dialog via modals.close_active.
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

export type DialogWidgetConfig = {
    html_heading: string;
    html_body: string;
    on_click: (e: unknown) => void;
    html_submit_button?: string;
    html_exit_button?: string;
    close_on_submit?: boolean;
    focus_submit_on_open?: boolean;
    help_link?: string;
    id?: string;
    single_footer_button?: boolean;
    form_id?: string;
    validate_input?: (e: unknown) => boolean;
    on_show?: () => void;
    on_shown?: () => void;
    on_hide?: () => void;
    on_hidden?: () => void;
    post_render?: () => void;
    loading_spinner?: boolean;
    update_submit_disabled_state_on_change?: boolean;
    always_visible_scrollbar?: boolean;
};

type RequestOpts = {
    failure_msg_html?: string;
    success_continuation?: Parameters<AjaxRequestHandler>[0]["success"];
    error_continuation?: Parameters<AjaxRequestHandler>[0]["error"];
};

export function hide_dialog_spinner(): void {
    $(".dialog_submit_button span").show();
    $("#dialog_widget_modal .modal__btn").prop("disabled", false);

    const $spinner = $("#dialog_widget_modal .modal__spinner");
    loading.destroy_indicator($spinner);
}

export function show_dialog_spinner(): void {
    // Disable both the buttons.
    $("#dialog_widget_modal .modal__btn").prop("disabled", true);

    const $spinner = $("#dialog_widget_modal .modal__spinner");
    const dialog_submit_button_span_width = $(".dialog_submit_button span").width();
    const dialog_submit_button_span_height = $(".dialog_submit_button span").height();

    // Hide the submit button after computing its height, since submit
    // buttons with long text might affect the size of the button.
    $(".dialog_submit_button span").hide();

    loading.make_indicator($spinner, {
        width: dialog_submit_button_span_width,
        height: dialog_submit_button_span_height,
    });
}

// Supports a callback to be called once the modal finishes closing.
export function close(on_hidden_callback?: () => void): void {
    modals.close("dialog_widget_modal", {on_hidden: on_hidden_callback});
}

export function launch(conf: DialogWidgetConfig): void {
    // Mandatory fields:
    // * html_heading
    // * html_body
    // * on_click
    // The html_ fields should be safe HTML. If callers
    // interpolate user data into strings, they should use
    // templates.

    // Optional parameters:
    // * html_submit_button: Submit button text.
    // * html_exit_button: Exit button text.
    // * close_on_submit: Whether to close modal on clicking submit.
    // * focus_submit_on_open: Whether to focus submit button on open.
    // * help_link: A help link in the heading area.
    // * id: Custom id to the container element to modify styles.
    // * single_footer_button: If true, don't include the "Cancel" button.
    // * form_id: Id of the form element in the modal if it exists.
    // * validate_input: Function to validate the input of the modal.
    // * on_show: Callback to run when the modal is triggered to show.
    // * on_shown: Callback to run when the modal is shown.
    // * on_hide: Callback to run when the modal is triggered to hide.
    // * on_hidden: Callback to run when the modal is hidden.
    // * post_render: Callback to run after the modal body is added to DOM.
    // * loading_spinner: Whether to show a loading spinner inside the
    //   submit button when clicked.
    // * update_submit_disabled_state_on_change: If true, updates state of submit button
    //   on valid input change in modal.
    // * always_visible_scrollbar: Whether the scrollbar is always visible if modal body
    //   has scrollable content. Default behaviour is to hide the scrollbar when it is
    //   not in use.

    const html_submit_button = conf.html_submit_button ?? $t_html({defaultMessage: "Save changes"});
    const html_exit_button = conf.html_exit_button ?? $t_html({defaultMessage: "Cancel"});
    const html = render_dialog_widget({
        heading_text: conf.html_heading,
        link: conf.help_link,
        html_submit_button,
        html_exit_button,
        html_body: conf.html_body,
        id: conf.id,
        single_footer_button: conf.single_footer_button,
        always_visible_scrollbar: conf.always_visible_scrollbar,
    });
    const $dialog = $(html);
    $("body").append($dialog);

    if (conf.post_render !== undefined) {
        conf.post_render();
    }

    const $submit_button = $dialog.find(".dialog_submit_button");

    function get_current_values($inputs: JQuery): Record<string, unknown> {
        const current_values: Record<string, unknown> = {};
        $inputs.each(function () {
            const property_name = $(this).attr("name")!;
            if (property_name) {
                if (
                    this instanceof HTMLInputElement &&
                    this.type === "file" &&
                    this.files?.length
                ) {
                    // If the input is a file input and a file has been selected, set value to file object
                    current_values[property_name] = this.files[0];
                } else if (property_name === "edit_bot_owner") {
                    current_values[property_name] = $(this).find(".dropdown_widget_value").text();
                } else {
                    current_values[property_name] = $(this).val();
                }
            }
        });
        return current_values;
    }

    if (conf.update_submit_disabled_state_on_change) {
        const $inputs = $dialog.find(".modal__content").find("input,select,textarea,button");

        const original_values = get_current_values($inputs);

        $submit_button.prop("disabled", true);

        $inputs.on("input", () => {
            const current_values = get_current_values($inputs);

            if (!_.isEqual(original_values, current_values)) {
                $submit_button.prop("disabled", false);
            } else {
                $submit_button.prop("disabled", true);
            }
        });
    }

    // This is used to link the submit button with the form, if present, in the modal.
    // This makes it so that submitting this form by pressing Enter on an input element
    // triggers a click on the submit button.
    if (conf.form_id) {
        $submit_button.attr("form", conf.form_id);
    }

    // Set up handlers.
    $submit_button.on("click", (e) => {
        e.preventDefault();

        if (conf.validate_input && !conf.validate_input(e)) {
            return;
        }
        if (conf.loading_spinner) {
            show_dialog_spinner();
        } else if (conf.close_on_submit) {
            close();
        }
        $("#dialog_error").hide();
        conf.on_click(e);
    });

    modals.open("dialog_widget_modal", {
        autoremove: true,
        on_show() {
            if (conf.focus_submit_on_open) {
                $submit_button.trigger("focus");
            }
            if (conf.on_show) {
                conf.on_show();
            }
        },
        on_hide: conf?.on_hide,
        on_shown: conf?.on_shown,
        on_hidden: conf?.on_hidden,
    });
}

export function submit_api_request(
    request_method: AjaxRequestHandler,
    url: string,
    data: Omit<Parameters<AjaxRequestHandler>[0]["data"], "undefined">,
    {
        failure_msg_html = $t_html({defaultMessage: "Failed"}),
        success_continuation,
        error_continuation,
    }: RequestOpts = {},
): void {
    show_dialog_spinner();
    void request_method({
        url,
        data,
        success(response_data, textStatus, jqXHR) {
            close();
            if (success_continuation !== undefined) {
                success_continuation(response_data, textStatus, jqXHR);
            }
        },
        error(xhr, error_type, xhn) {
            ui_report.error(failure_msg_html, xhr, $("#dialog_error"));
            hide_dialog_spinner();
            if (error_continuation !== undefined) {
                error_continuation(xhr, error_type, xhn);
            }
        },
    });
}
