import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_add_rsvp_meeting_modal from "../templates/add_rsvp_meeting_modal.hbs";

import * as add_meeting from "./add_meeting.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as pill_typeahead from "./pill_typeahead.ts";
import * as timerender from "./timerender.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as user_pill from "./user_pill.ts";
import * as flatpickr from "./flatpickr.ts";
import * as util from "./util.ts";

let add_meeting_widget: dropdown_widget.DropdownWidget | undefined;
let add_meeting_dropdown: tippy.Instance | undefined;
let composebox_add_meeting_dropdown_widget = false;

function submit_rsvp_meeting_form(): void {
  const topic = $<HTMLInputElement>("#rsvp-meeting-topic").val()?.trim();
  const datetime = $<HTMLInputElement>("#rsvp-meeting-datetime-value")
    .val()
    ?.trim();

  assert(topic && datetime);

  // TODO: submit the RSVP meeting via API
  // dialog_widget.submit_api_request(channel.post, "/json/meetings/rsvp", {topic, datetime});

  const invitee_ids = user_pill.get_user_ids(invite_users_widget);

  console.log({topic, datetime, invitee_ids});
}

function update_rsvp_submit_button_state(): void {
  const topic = $<HTMLInputElement>("#rsvp-meeting-topic").val()?.trim();
  const datetime = $<HTMLInputElement>("#rsvp-meeting-datetime-value")
    .val()
    ?.trim();

  const $submit_button = $("#add-rsvp-meeting-modal .dialog_submit_button");

  $submit_button.prop("disabled", true);
  if (topic && datetime) {
    $submit_button.prop("disabled", false);
  }
}

function populate_user_dropdown(): void {
  const stream_id = narrow_state.stream_id();
  const $dropdown = $("#rsvp-user-dropdown");

  $dropdown.empty();

  let users: people.User[] = [];

  if (stream_id) {
    const user_ids = peer_data.get_subscriber_ids_assert_loaded(stream_id);
    for (const id of user_ids) {
      const user = people.get_by_user_id(id);
      if (user) {
        users.push(user);
      }
    }
  } else {
    users = people.get_realm_users();
  }

  if (users.length === 0) {
    $dropdown.append(
      `<div class="rsvp-user-option disabled">${$t({
        defaultMessage: "No users available",
      })}</div>`,
    );
    return;
  }

  for (const user of users) {
    const item: user_pill.UserPillData = {
      type: "user",
      user,
    };

    const html = typeahead_helper.render_person(item);
    const $option = $(`<div class="rsvp-user-option">${html}</div>`);

    $option.on("click", () => {
      user_pill.append_user(user, invite_users_widget);
      $("#rsvp-user-dropdown").hide();
    });

    $dropdown.append($option);
  }
}

let invite_users_widget: any;

function rsvp_meeting_modal_post_render(): void {
  $("#add-rsvp-meeting-modal").on(
    "input",
    "input,textarea",
    update_rsvp_submit_button_state,
  );
  $("#rsvp-add-all-users").on("click", on_add_all_users_click);

  invite_users_widget = user_pill.create_pills(
    $("#rsvp-invite-users-container"),
  );

  pill_typeahead.set_up_user($("#rsvp-invite-users"), invite_users_widget, {
    exclude_bots: false,
  });

  $("#rsvp-invite-users").on("focus", () => {
    $("#rsvp-invite-users").trigger("input");
  });

  $("#rsvp-user-dropdown-button").on("click", () => {
    const $dropdown = $("#rsvp-user-dropdown");

    if ($dropdown.is(":visible")) {
      $dropdown.hide();
      return;
    }

    populate_user_dropdown();
    $dropdown.show();
  });

  // open flatpickr calendar when clicking the datetime input and populate it
  $("#add-rsvp-meeting-modal").on("click", "#rsvp-meeting-datetime", (e) => {
    e.preventDefault();
    e.stopPropagation();

    const $input = $(e.currentTarget);

    const defaultDate = ((): Date => {
      const cur = $<HTMLInputElement>("#rsvp-meeting-datetime-value").val() as
        | string
        | undefined;
      if (cur) {
        const parsed = new Date(cur);
        if (!Number.isNaN(parsed.getTime())) {
          return parsed;
        }
      }
      return new Date();
    })();

    flatpickr.show_flatpickr(
      util.the($input),
      (selectedDate) => {
        const dt = new Date(selectedDate);
        const tzOffsetMs = dt.getTimezoneOffset() * 60 * 1000;
        const localDt = new Date(dt.getTime() - tzOffsetMs);
        const isoValue = localDt.toISOString().slice(0, 16);

        // Show human-readable string in the visible text input
        const formatted = timerender.get_full_datetime(dt, "time");
        $input.val(formatted);

        // Store ISO value in hidden input — this is what submit/validation reads
        $("#rsvp-meeting-datetime-value").val(isoValue).trigger("input");

        update_rsvp_submit_button_state();
      },
      defaultDate,
      {
        enableTime: true,
        minDate: new Date(),
        appendTo: document.body,
        onOpen: (_selectedDates, _dateStr, instance) => {
          const inputEl = util.the($input); // same $input you passed to show_flatpickr
          const rect = inputEl.getBoundingClientRect();
          const cal = instance.calendarContainer;
          cal.classList.remove(
            "arrowTop",
            "arrowBottom",
            "arrowLeft",
            "arrowRight",
          );
          cal.style.position = "fixed";
          cal.style.transform = "none";
          cal.style.zIndex = "6000";

          // Defer measurement until after the calendar has fully rendered
          // so offsetWidth/offsetHeight return correct values
          setTimeout(() => {
            const spacing = 8;
            const calWidth = cal.offsetWidth;
            const calHeight = cal.offsetHeight;
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            // Try placing to the right of the input first
            let left = rect.right + spacing;
            let top = rect.top;

            // If it overflows the right edge, place to the left instead
            if (left + calWidth > viewportWidth - spacing) {
              left = rect.left - calWidth - spacing;
            }

            // If it overflows the bottom, shift up so it fits
            if (top + calHeight > viewportHeight - spacing) {
              top = viewportHeight - calHeight - spacing;
            }

            // Never go above the top of the viewport
            if (top < spacing) {
              top = spacing;
            }

            cal.style.left = `${left}px`;
            cal.style.top = `${top}px`;
          }, 0);
        },
      },
    );
  });
}

function on_add_all_users_click(): void {
  // TODO: populate invite users field with all users in the current channel
  const users = people.get_realm_users();

  if (!invite_users_widget) {
    return;
  }

  for (const user of users) {
    user_pill.append_user(user, invite_users_widget);
  }
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

export function setup_add_meeting_dropdown_widget(
  widget_selector: string,
): void {
  new dropdown_widget.DropdownWidget({
    widget_name: "add_meeting",
    widget_selector,
    get_options: add_meeting.get_options_for_dropdown_widget,
    item_click_callback,
    $events_container: $("body"),
    unique_id_type: "number",
    on_show_callback(
      dropdown: tippy.Instance,
      widget: dropdown_widget.DropdownWidget,
    ) {
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
