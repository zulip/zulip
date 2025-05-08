import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_dialog_widget from "../templates/dialog_widget.hbs";

import type {AjaxRequestHandler} from "./channel.ts";
import * as custom_profile_fields_ui from "./custom_profile_fields_ui.ts";
import {$t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as modals from "./modals.ts";
import * as ui_report from "./ui_report.ts";

// Since only one dialog widget can be active at a time
// and we don't support reopening already closed dialog widgets,
// this is also the id of the current / last open dialog widget.
// We will use this as id for current dialog widget assuming
// the caller has already checked that the dialog widget is open.
let widget_id_counter = 0;

function current_dialog_widget_id(): string {
    return `dialog_widget_modal_${widget_id_counter}`;
}

function current_dialog_widget_selector(): string {
    return `#${CSS.escape(current_dialog_widget_id())}`;
}

/*
 *  Look for dialog_widget or confirm_dialog in various
 *  'web/src/' files to see examples of how to use this widget.
 *  It's pretty simple to use!
 *
 *  Some things to note:
 *      1) We create DOM on the fly, and we remove
 *         the DOM once it's closed.
 *
 *      2) We attach the DOM for the modal to the body element
 *         to avoid interference from other elements.
 *
 *      3) For settings, we have a click handler in settings.ts
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
    html_heading?: string;
    text_heading?: string;
    html_body: string;
    on_click: (e: JQuery.ClickEvent) => void;
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
    post_render?: (modal_unique_id: string) => void;
    loading_spinner?: boolean;
    update_submit_disabled_state_on_change?: boolean;
    always_visible_scrollbar?: boolean;
    footer_minor_text?: string;
    close_on_overlay_click?: boolean;
};

type RequestOpts = {
    failure_msg_html?: string;
    success_continuation?: Parameters<AjaxRequestHandler>[0]["success"];
    error_continuation?: Parameters<AjaxRequestHandler>[0]["error"];
};

export function hide_dialog_spinner(): void {
    const dialog_widget_selector = current_dialog_widget_selector();
    const $spinner = $(`${dialog_widget_selector} .modal__spinner`);
    $(`${dialog_widget_selector} .modal__button`).prop("disabled", false);

    loading.hide_spinner($(".dialog_submit_button"), $spinner);
}

export function show_dialog_spinner(): void {
    const dialog_widget_selector = current_dialog_widget_selector();
    // Disable both the buttons.
    $(`${dialog_widget_selector} .modal__button`).prop("disabled", true);

    const $spinner = $(`${dialog_widget_selector} .modal__spinner`);

    loading.show_spinner($(".dialog_submit_button"), $spinner);
}

// Supports a callback to be called once the modal finishes closing.
export function close(on_hidden_callback?: () => void): void {
    modals.close(current_dialog_widget_id(), {on_hidden: on_hidden_callback});
}

export function get_current_values($inputs: JQuery): Record<string, unknown> {
    const current_values: Record<string, unknown> = {};
    $inputs.each(function () {
        const property_name = $(this).attr("name")!;
        if (property_name) {
            if (this instanceof HTMLInputElement && this.type === "file" && this.files?.length) {
                // If the input is a file input and a file has been selected, set value to file object
                current_values[property_name] = this.files[0];
            } else if (this instanceof HTMLInputElement && this.type === "checkbox") {
                // If the input is a checkbox, check the inputs `checked` attribute.
                current_values[property_name] = this.checked;
            } else if (property_name === "edit_bot_owner") {
                current_values[property_name] = $(this).find(".dropdown_widget_value").text();
            } else if ($(this).hasClass("pill-container")) {
                // Notably, this just concatenates the pill labels;
                // good enough for checking if something has changed,
                // but not appropriate for many other potential uses.
                current_values[property_name] = $(this).find(".pill-value").text();
            } else {
                current_values[property_name] = $(this).val();
            }
        }

        if ($(this).hasClass("date-field-alt-input")) {
            // For date type custom profile fields, we convert the
            // input to the date format passed to the API.
            const value = $(this).val()!;
            const name = $(this).parent().find(".custom_user_field_value").attr("name")!;

            if (value === "") {
                // This case is handled separately, because it will
                // otherwise be parsed as an invalid date.
                current_values[name] = value;
                return;
            }

            assert(typeof value === "string");
            const date_str = new Date(value);
            current_values[name] = custom_profile_fields_ui.format_date(date_str, "Y-m-d");
        }
    });
    return current_values;
}

export function launch(conf: DialogWidgetConfig): string {
    // Mandatory fields:
    // * html_heading | text_heading
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
    // * close_on_overlay_click: Whether to close modal on clicking overlay.

    widget_id_counter += 1;
    const modal_unique_id = current_dialog_widget_id();
    const html_submit_button = conf.html_submit_button ?? $t_html({defaultMessage: "Save changes"});
    const html_exit_button = conf.html_exit_button ?? $t_html({defaultMessage: "Cancel"});
    const html = render_dialog_widget({
        modal_unique_id,
        html_heading: conf.html_heading,
        text_heading: conf.text_heading,
        link: conf.help_link,
        html_submit_button,
        html_exit_button,
        html_body: conf.html_body,
        id: conf.id,
        single_footer_button: conf.single_footer_button,
        always_visible_scrollbar: conf.always_visible_scrollbar,
        footer_minor_text: conf.footer_minor_text,
        close_on_overlay_click: conf.close_on_overlay_click ?? true,
    });
    const $dialog = $(html);
    $("body").append($dialog);

    setTimeout(() => {
        if (conf.post_render !== undefined) {
            conf.post_render(modal_unique_id);
        }
    }, 0);

    const $submit_button = $dialog.find(".dialog_submit_button");

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

    modals.open(modal_unique_id, {
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
    return modal_unique_id;
}

export function submit_api_request(
    request_method: AjaxRequestHandler,
    url: string,
    data: Record<string, unknown>,
    {
        failure_msg_html = $t_html({defaultMessage: "Failed"}),
        success_continuation,
        error_continuation,
    }: RequestOpts = {},
    close_on_success = true,
): void {
    show_dialog_spinner();
    void request_method({
        url,
        data,
        success(response_data, textStatus, jqXHR) {
            if (close_on_success) {
                close();
            } else {
                hide_dialog_spinner();
            }

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
