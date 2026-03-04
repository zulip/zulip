import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_add_rsvp_meeting_modal from "../templates/add_rsvp_meeting_modal.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as rows from "./rows.ts";
import * as add_meeting from "./add_meeting.ts";

let add_meeting_widget: dropdown_widget.DropdownWidget | undefined;
let add_meeting_dropdown: tippy.Instance | undefined;
let composebox_add_meeting_dropdown_widget = false;

function submit_rsvp_meeting_form(): void {
    const topic = $<HTMLInputElement>("#add-rsvp-meeting-modal .rsvp-meeting-topic")
        .val()
        ?.trim();
    const datetime = $<HTMLInputElement>("#add-rsvp-meeting-modal .rsvp-meeting-datetime")
        .val()
        ?.trim();

    assert(topic && datetime);

    // TODO: submit the RSVP meeting via API
    // dialog_widget.submit_api_request(channel.post, "/json/meetings/rsvp", {topic, datetime});
}

function update_rsvp_submit_button_state(): void {
    const topic = $<HTMLInputElement>("#add-rsvp-meeting-modal .rsvp-meeting-topic")
        .val()
        ?.trim();
    const datetime = $<HTMLInputElement>("#add-rsvp-meeting-modal .rsvp-meeting-datetime")
        .val()
        ?.trim();
    const $submit_button = $("#add-rsvp-meeting-modal .dialog_submit_button");

    $submit_button.prop("disabled", true);
    if (topic && datetime) {
        $submit_button.prop("disabled", false);
    }
}

function rsvp_meeting_modal_post_render(): void {
    $("#add-rsvp-meeting-modal").on("input", "input,textarea", update_rsvp_submit_button_state);
    $("#rsvp-add-all-users").on("click", on_add_all_users_click);
}

function on_add_all_users_click(): void {
    // TODO: populate invite users field with all users in the current channel
}

function item_click_callback(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
    _is_sticky_bottom_option_clicked: boolean,
): void {
    event.preventDefault();
    event.stopPropagation();

    dropdown.hide();

    const current_value = widget.current_value;
    assert(typeof current_value === "number");

    if (current_value === add_meeting.OPTION_RSVP_MEETING) {
        dialog_widget.launch({
            modal_title_html: $t_html({defaultMessage: "Meeting RSVP"}),
            modal_content_html: render_add_rsvp_meeting_modal({}),
            modal_submit_button_text: $t({defaultMessage: "Submit"}),
            id: "add-rsvp-meeting-modal",
            form_id: "rsvp-meeting-form",
            update_submit_disabled_state_on_change: true,
            on_click: submit_rsvp_meeting_form,
            on_shown: () => $("#rsvp-meeting-topic").trigger("focus"),
            post_render: rsvp_meeting_modal_post_render,
        });
    } else if (current_value === add_meeting.OPTION_PROPOSE_MEETING) {
        // TODO: implement "Propose a meeting" flow
    }
}

export function setup_add_meeting_dropdown_widget(widget_selector: string): void {
    new dropdown_widget.DropdownWidget({
        widget_name: "add_meeting",
        widget_selector,
        get_options: add_meeting.get_options_for_dropdown_widget,
        item_click_callback,
        $events_container: $("body"),
        unique_id_type: "number",
        on_show_callback(dropdown: tippy.Instance, widget: dropdown_widget.DropdownWidget) {
            add_meeting_widget = widget;
            add_meeting_dropdown = dropdown;
        },
        focus_target_on_hidden: false,
        prefer_top_start_placement: true,
        tippy_props: {
            offset: [-100, 5],
        },
    }).setup();
}

export function setup_add_meeting_dropdown_widget_if_needed(): void {
    if (!composebox_add_meeting_dropdown_widget) {
        composebox_add_meeting_dropdown_widget = true;
        setup_add_meeting_dropdown_widget(".add-meeting-composebox-widget");
    }
}