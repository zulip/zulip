import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_add_rsvp_meeting_modal from "../templates/add_rsvp_meeting_modal.hbs";

import * as add_meeting from "./add_meeting.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as modals from "./modals.ts";
import * as hash_util from "./hash_util.ts";
import * as browser_history from "./browser_history.ts";
import * as narrow_state from "./narrow_state.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as timerender from "./timerender.ts";
import * as user_pill from "./user_pill.ts";
import * as flatpickr from "./flatpickr.ts";
import * as util from "./util.ts";
import * as compose_state from "./compose_state.ts";

let add_meeting_widget: dropdown_widget.DropdownWidget | undefined;
let add_meeting_dropdown: tippy.Instance | undefined;
let composebox_add_meeting_dropdown_widget = false;

function submit_rsvp_meeting_form(): void {
  const topic = $<HTMLInputElement>("#rsvp-meeting-topic").val()?.trim();
  const datetime = $<HTMLInputElement>("#rsvp-meeting-datetime-value")
    .val()
    ?.trim();
  assert(topic && datetime);

  const invitee_ids = user_pill.get_user_ids(invite_users_widget);
  const stream_id = narrow_state.stream_id();
  assert(stream_id !== undefined);

  const create_new_channel = $<HTMLInputElement>("#rsvp-create-channel").prop(
    "checked",
  ) as boolean;

  const extra_data = {
    widget_type: "rsvp",
    extra_data: {
      topic,
      datetime,
      invitees: invitee_ids,
    },
  };

  const send_message = (target_stream_id: number): void => {
    void channel.post({
      url: "/json/messages",
      data: {
        type: "stream",
        to: target_stream_id,
        topic,
        content: "/rsvp",
        widget_content: JSON.stringify(extra_data),
      },
      success() {
        modals.close_if_open("add-rsvp-meeting-modal");
        const url = hash_util.by_stream_topic_url(target_stream_id, topic);
        browser_history.go_to_location(url);
      },
    });
  };

  if (create_new_channel) {
    // Step 1: Create the new stream, then post the message to it
    void channel.post({
      url: "/json/users/me/subscriptions",
      data: {
        subscriptions: JSON.stringify([{name: topic}]),
        principals: JSON.stringify([
          people.my_current_user_id(),
          ...invitee_ids,
        ]),
        announce: false,
      },
      success() {
        // Find the new stream id by looking it up by name
        void channel.get({
          url: "/json/streams",
          data: {include_subscribed: true},
          success(streams_data) {
            const streams = (
              streams_data as {streams: {stream_id: number; name: string}[]}
            ).streams;
            const new_stream = streams.find((s) => s.name === topic);
            if (new_stream) {
              send_message(new_stream.stream_id);
            }
          },
        });
      },
    });
  } else {
    send_message(stream_id);
  }
}

function update_rsvp_submit_button_state(): void {
  const topic = $<HTMLInputElement>("#rsvp-meeting-topic").val()?.trim();
  const datetime = $<HTMLInputElement>("#rsvp-meeting-datetime-value")
    .val()
    ?.trim();
  const has_invitees = user_pill.get_user_ids(invite_users_widget).length > 0;
  const stream_id = narrow_state.stream_id();

  const $submit_button = $("#add-rsvp-meeting-modal .dialog_submit_button");
  const is_disabled = !topic || !datetime || !has_invitees || stream_id === undefined;

  $submit_button.prop("disabled", is_disabled);
}

function populate_user_dropdown(): void {
  const $dropdown = $("#rsvp-user-dropdown");

  $dropdown.empty();

  const already_added_ids = new Set(
    user_pill.get_user_ids(invite_users_widget),
  );
  const users = people
    .get_realm_users()
    .filter((user) => !already_added_ids.has(user.user_id));

  if (users.length === 0) {
    $dropdown.append(
      `<div class="rsvp-user-option disabled">${$t({
        defaultMessage: "No users available",
      })}</div>`,
    );
    return;
  }

  for (const user of users) {
    const html = `
        <div class="rsvp-user-item">
            <img src="${user.avatar_url}" class="avatar" />
            <div class="user-info">
                <div class="user-name">${user.full_name}</div>
                <div class="user-email">${user.email}</div>
            </div>
        </div>
    `;

    const $option = $(`
      <div class="rsvp-user-option horizontal-user">
        ${html}
      </div>
    `);

    $option.on("click", () => {
      user_pill.append_user(user, invite_users_widget);
      $dropdown.hide();
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

  invite_users_widget.onPillCreate(() => {
    $("#rsvp-invite-users").removeAttr("data-placeholder");
    update_channel_warning();
    update_rsvp_submit_button_state();
  });

  invite_users_widget.onPillRemove(() => {
    if (user_pill.get_user_ids(invite_users_widget).length === 0) {
      $("#rsvp-invite-users").attr(
        "data-placeholder",
        $t({defaultMessage: "Add users"}),
      );
    }
    update_channel_warning();
    update_rsvp_submit_button_state();
  });

  $(document).on("click.rsvp-dropdown", (e) => {
    const $dropdown = $("#rsvp-user-dropdown");
    if (
      $dropdown.is(":visible") &&
      !$(e.target).closest(
        "#rsvp-user-dropdown, #rsvp-invite-users-container, #rsvp-user-dropdown-button",
      ).length
    ) {
      $dropdown.hide();
    }
  });

  $("#rsvp-invite-users").on("input", () => {
    const query = ($("#rsvp-invite-users").text() ?? "").toLowerCase().trim();
    const $dropdown = $("#rsvp-user-dropdown");

    if (!query) {
      $dropdown.hide();
      return;
    }

    populate_user_dropdown();

    $dropdown.find(".rsvp-user-option").each(function () {
      const name = $(this).find(".user-name").text().toLowerCase();
      const email = $(this).find(".user-email").text().toLowerCase();
      $(this).toggle(name.includes(query) || email.includes(query));
    });

    const containerEl = $("#rsvp-invite-users-container")[0];
    if (containerEl) {
      const rect = containerEl.getBoundingClientRect();
      const dropdownEl = $dropdown[0];
      if (dropdownEl) {
        $dropdown.show();
        const dropdownHeight = dropdownEl.offsetHeight;
        $dropdown.css({
          top: rect.top - dropdownHeight - 4,
          left: rect.left,
          width: rect.width,
        });
      }
    }
  });

  $("#rsvp-invite-users").on("click focus", () => {
    $("#rsvp-user-dropdown").hide();
  });

  $("#rsvp-user-dropdown-button").on("click", () => {
    const $dropdown = $("#rsvp-user-dropdown");

    if ($dropdown.is(":visible")) {
      $dropdown.hide();
      return;
    }

    populate_user_dropdown();

    const $container = $("#rsvp-invite-users-container");
    const containerEl = $container[0];
    if (!containerEl) {
      return;
    }
    const rect = containerEl.getBoundingClientRect();
    const dropdownEl = $dropdown[0];

    if (!dropdownEl) {
      return;
    }
    $dropdown.show();
    const dropdownHeight = dropdownEl.offsetHeight;
    $dropdown.css({
      top: rect.top - dropdownHeight - 4,
      left: rect.left,
      width: rect.width,
    });
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
        // Use defaultDate as minDate to prevent slight pass of time from erroring
        minDate: defaultDate,
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

  // Set initial submit button state (may be disabled if not in a channel narrow)
  update_rsvp_submit_button_state();
}

function on_add_all_users_click(): void {
  const stream_id = narrow_state.stream_id();

  if (!invite_users_widget || !stream_id) {
    return;
  }

  const already_added_ids = new Set(
    user_pill.get_user_ids(invite_users_widget),
  );
  const user_ids = peer_data.get_subscriber_ids_assert_loaded(stream_id);

  for (const id of user_ids) {
    if (already_added_ids.has(id)) {
      continue;
    }

    const user = people.get_by_user_id(id);
    if (user) {
      user_pill.append_user(user, invite_users_widget);
    }
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
  widget.current_value = undefined;
  assert(typeof current_value === "number");

  if (current_value === add_meeting.OPTION_RSVP_MEETING) {
    // RESTRICTIVE CHECK: Ensure we are in a valid channel narrow
    const is_in_channel_narrow = narrow_state.stream_id() !== undefined;
    const is_stream_mode = compose_state.get_message_type() === "stream";
    const selected_stream_id = compose_state.stream_id();
    const has_real_stream = selected_stream_id !== undefined && selected_stream_id !== 0;

    // Must be in a channel view AND composing to a valid channel
    if (!is_in_channel_narrow || !is_stream_mode || !has_real_stream) {
        return;
    }

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
      on_hide() {
        $("#rsvp-user-dropdown").hide();
        $(document).off("click.rsvp-dropdown");
      },
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

function update_channel_warning(): void {
  const stream_id = narrow_state.stream_id();
  const $warning = $("#rsvp-channel-warning");
  const $checkbox = $<HTMLInputElement>("#rsvp-create-channel");

  if (!stream_id) {
    $warning.hide();
    $checkbox.prop("checked", false).prop("disabled", false);
    return;
  }

  const subscriber_ids = new Set(
    peer_data.get_subscriber_ids_assert_loaded(stream_id),
  );
  const invited_ids = user_pill.get_user_ids(invite_users_widget);
  const has_outside_user = invited_ids.some((id) => !subscriber_ids.has(id));

  if (has_outside_user) {
    $warning.show();
    $checkbox.prop("checked", true).prop("disabled", true);
    $checkbox.closest("label").addClass("disabled");
  } else {
    $warning.hide();
    $checkbox.prop("checked", false).prop("disabled", false);
    $checkbox.closest("label").removeClass("disabled");
  }
}

export const __test_only = {
    set_invite_users_widget: (w: any) => { invite_users_widget = w; },
    on_add_all_users_click,
    update_rsvp_submit_button_state,
    reset_composebox_widget_flag: () => { composebox_add_meeting_dropdown_widget = false; },
    get_composebox_widget_flag: () => composebox_add_meeting_dropdown_widget,
};
