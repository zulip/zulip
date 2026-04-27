import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_add_rsvp_meeting_modal from "../templates/add_rsvp_meeting_modal.hbs";
import render_add_propose_meeting_modal from "../templates/add_propose_meeting_modal.hbs";

import * as add_meeting from "./add_meeting.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import { $t, $t_html } from "./i18n.ts";
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
        subscriptions: JSON.stringify([{ name: topic }]),
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
          data: { include_subscribed: true },
          success(streams_data) {
            const streams = (
              streams_data as { streams: { stream_id: number; name: string }[] }
            ).streams;
            const new_stream = streams.find((s) => s.name === topic);
            if (new_stream) {
              send_message(new_stream.stream_id);
            } else {
              // The stream was created but cannot be found by name in the
              // subscribed list. Close the modal so the user can investigate.
              modals.close_if_open("add-rsvp-meeting-modal");
            }
          },
        });
      },
    });
  } else {
    send_message(stream_id);
  }
}

function submit_propose_meeting_form(): void {
  const topic = $<HTMLInputElement>("#propose-meeting-topic").val()?.trim();
  const dates_raw = $<HTMLInputElement>("#propose-meeting-dates-value").val()?.trim();
  const times_raw = $<HTMLInputElement>("#propose-meeting-times-value").val()?.trim();
  const rsvp_by = $<HTMLInputElement>("#propose-rsvp-by-value").val()?.trim();
  assert(topic && dates_raw && times_raw && rsvp_by);

  const invitee_ids = user_pill.get_user_ids(invite_users_widget);
  const create_new_channel = $<HTMLInputElement>("#propose-create-channel").prop("checked") as boolean;
  const stream_id = narrow_state.stream_id();

  if (!create_new_channel && stream_id === undefined) {
    return;
  }

  const dates = dates_raw.split(",").map((s) => s.trim()).filter(Boolean);
  const times = times_raw.split(",").map((s) => s.trim()).filter(Boolean);
  const slots: { start_time: string }[] = [];
  for (const date of dates) {
    for (const time of times) {
      slots.push({ start_time: new Date(`${date}T${time}:00`).toISOString() });
    }
  }

  const invitee_names = invitee_ids
    .map((id) => people.get_by_user_id(id)?.full_name ?? String(id))
    .join(", ");

  const send_message = (target_stream_id: number, meeting_id: number): void => {
    const extra_data = {
      widget_type: "propose_meeting",
      extra_data: {
        meeting_id,
        topic,
        invitees: invitee_ids,
      },
    };

    void channel.post({
      url: "/json/messages",
      data: {
        type: "stream",
        to: target_stream_id,
        topic,
        content: "/propose_meeting",
        widget_content: JSON.stringify(extra_data),
      },
      success() {
        modals.close_if_open("add-propose-meeting-modal");
        const url = hash_util.by_stream_topic_url(target_stream_id, topic);
        browser_history.go_to_location(url);
      },
      error() {
        // The meeting was created on the server but the widget message
        // could not be posted. Navigate to the channel so the user
        // can see the state and manually retry posting.
        modals.close_if_open("add-propose-meeting-modal");
        const url = hash_util.by_stream_topic_url(target_stream_id, topic);
        browser_history.go_to_location(url);
      },
    });
  };

  void channel.post({
    url: "/json/meetings",
    data: {
      topic,
      slots: JSON.stringify(slots),
      deadline: rsvp_by,
      invite_user_ids: JSON.stringify(invitee_ids),
      create_channel: JSON.stringify(create_new_channel),
      stream_id: create_new_channel ? undefined : stream_id,
    },
    success(data) {
      const result = data as { meeting_id: number; stream_id: number };
      // Disable submit to prevent a duplicate meeting if the message send fails.
      $("#add-propose-meeting-modal .dialog_submit_button").prop("disabled", true);
      send_message(result.stream_id, result.meeting_id);
    },
  });
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

function update_propose_submit_button_state(): void {
  const topic = $<HTMLInputElement>("#propose-meeting-topic").val()?.trim();
  const dates = $<HTMLInputElement>("#propose-meeting-dates-value").val()?.trim();
  const times = $<HTMLInputElement>("#propose-meeting-times-value").val()?.trim();
  const rsvp_by = $<HTMLInputElement>("#propose-rsvp-by-value").val()?.trim();
  const has_invitees = user_pill.get_user_ids(invite_users_widget).length > 0;
  const create_new_channel = $<HTMLInputElement>("#propose-create-channel").prop("checked") as boolean;
  const stream_id = narrow_state.stream_id();

  const $submit_button = $("#add-propose-meeting-modal .dialog_submit_button");
  $submit_button.prop(
    "disabled",
    !topic || !dates || !times || !rsvp_by || !has_invitees || (!create_new_channel && stream_id === undefined),
  );
}

function escape_html(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function populate_rsvp_user_dropdown(): void {
  const $dropdown = $("#rsvp-user-dropdown");

  $dropdown.empty();

  const already_added_ids = new Set(
    user_pill.get_user_ids(invite_users_widget),
  );
  const users = people
    .get_realm_users()
    .filter((user) => !already_added_ids.has(user.user_id) && !user.is_bot);

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
            <img src="${escape_html(user.avatar_url ?? "")}" class="avatar" />
            <div class="user-info">
                <div class="user-name">${escape_html(user.full_name)}</div>
                <div class="user-email">${escape_html(user.email)}</div>
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

function populate_propose_user_dropdown(): void {
  const $dropdown = $("#propose-user-dropdown");
  $dropdown.empty();

  const already_added_ids = new Set(user_pill.get_user_ids(invite_users_widget));
  const users = people.get_realm_users().filter((u) => !already_added_ids.has(u.user_id) && !u.is_bot);

  if (users.length === 0) {
    $dropdown.append(
      `<div class="rsvp-user-option disabled">${$t({ defaultMessage: "No users available" })}</div>`,
    );
    return;
  }

  for (const user of users) {
    const html = `
            <div class="rsvp-user-item">
                <img src="${escape_html(user.avatar_url ?? "")}" class="avatar" />
                <div class="user-info">
                    <div class="user-name">${escape_html(user.full_name)}</div>
                    <div class="user-email">${escape_html(user.email)}</div>
                </div>
            </div>`;

    const $option = $(`<div class="rsvp-user-option horizontal-user">${html}</div>`);

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
    update_rsvp_channel_warning();
    update_rsvp_submit_button_state();
  });

  invite_users_widget.onPillRemove(() => {
    if (user_pill.get_user_ids(invite_users_widget).length === 0) {
      $("#rsvp-invite-users").attr(
        "data-placeholder",
        $t({ defaultMessage: "Add users" }),
      );
    }
    update_rsvp_channel_warning();
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

    populate_rsvp_user_dropdown();

    const $options = $dropdown.find(".rsvp-user-option").toArray();
    const starts_with: HTMLElement[] = [];

    for (const el of $options) {
      const name = $(el).find(".user-name").text().toLowerCase();
      const email = $(el).find(".user-email").text().toLowerCase();
      if (name.startsWith(query) || email.startsWith(query)) {
        starts_with.push(el);
      }
    }

    $dropdown.empty();
    for (const el of starts_with) {
      $dropdown.append(el);
    }

    if (starts_with.length === 0) {
      $dropdown.hide();
      return;
    }

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

    populate_rsvp_user_dropdown();

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
        const isoValue = dt.toISOString();

        // Show human-readable string in the visible text input
        const formatted = timerender.get_full_datetime(dt, "time");
        $input.val(formatted);

        // Store UTC ISO value in hidden input — this is what submit/validation reads
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

function propose_meeting_modal_post_render(): void {
  function validate_propose_form(): void {
    const dates_raw = ($("#propose-meeting-dates-value").val() ?? "") as string;
    const times_raw = ($("#propose-meeting-times-value").val() ?? "") as string;
    const rsvp_by = ($("#propose-rsvp-by-value").val() ?? "") as string;
    const now = new Date();

    let dates_times_error = false;
    let rsvp_error = false;

    // check if any date + time combo is in the past
    if (dates_raw && times_raw) {
      const dates = dates_raw.split(",").map((s) => s.trim()).filter(Boolean);
      const times = times_raw.split(",").map((s) => s.trim()).filter(Boolean);
      for (const date of dates) {
        for (const time of times) {
          const dt = new Date(`${date}T${time}:00`);
          if (dt <= now) {
            dates_times_error = true;
            break;
          }
        }
        if (dates_times_error) break;
      }
    }

    // check if RSVP by is in the past
    if (rsvp_by) {
      const rsvp_dt = new Date(rsvp_by);
      if (rsvp_dt <= now) {
        rsvp_error = true;
      }
    }

    // show/hide errors
    const $dates_times_error = $("#propose-dates-times-error");
    const $rsvp_error = $("#propose-rsvp-error");

    if (dates_times_error) {
      $dates_times_error.show();
    } else {
      $dates_times_error.hide();
    }

    if (rsvp_error) {
      $rsvp_error.show();
    } else {
      $rsvp_error.hide();
    }

    const topic = ($<HTMLInputElement>("#propose-meeting-topic").val() ?? "").trim();
    const has_invitees = user_pill.get_user_ids(invite_users_widget).length > 0;
    const $submit_button = $("#add-propose-meeting-modal .dialog_submit_button");
    $submit_button.prop(
      "disabled",
      !topic || !dates_raw || !times_raw || !rsvp_by || !has_invitees || dates_times_error || rsvp_error,
    );
  }

  $(document).off("click.propose-pickers");
  $(".propose-time-picker").remove();

  $("#add-propose-meeting-modal").on("input", "input,textarea", validate_propose_form);
  $("#propose-add-all-users").on("click", on_add_all_users_click);

  invite_users_widget = user_pill.create_pills($("#propose-invite-users-container"));

  invite_users_widget.onPillCreate(() => {
    $("#propose-invite-users").removeAttr("data-placeholder");
    update_propose_channel_warning();
    update_propose_submit_button_state();
  });

  invite_users_widget.onPillRemove(() => {
    if (user_pill.get_user_ids(invite_users_widget).length === 0) {
      $("#propose-invite-users").attr("data-placeholder", $t({ defaultMessage: "Add users" }));
    }
    update_propose_channel_warning();
    update_propose_submit_button_state();
  });

  // close dropdown on outside click
  $(document).on("click.propose-dropdown", (e) => {
    const $dropdown = $("#propose-user-dropdown");
    if (
      $dropdown.is(":visible") &&
      !$(e.target).closest(
        "#propose-user-dropdown, #propose-invite-users-container, #propose-user-dropdown-button",
      ).length
    ) {
      $dropdown.hide();
    }
  });

  $("#propose-invite-users").on("input", () => {
    const query = ($("#propose-invite-users").text() ?? "").toLowerCase().trim();
    const $dropdown = $("#propose-user-dropdown");

    if (!query) {
      $dropdown.hide();
      return;
    }

    populate_propose_user_dropdown();

    $dropdown.find(".rsvp-user-option").each(function () {
      const name = $(this).find(".user-name").text().toLowerCase();
      const email = $(this).find(".user-email").text().toLowerCase();
      $(this).toggle(name.includes(query) || email.includes(query));
    });

    const containerEl = $("#propose-invite-users-container")[0];
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

  $("#propose-invite-users").on("click focus", () => {
    $("#propose-user-dropdown").hide();
  });

  // + button opens user dropdown
  $("#propose-user-dropdown-button").on("click", () => {
    const $dropdown = $("#propose-user-dropdown");
    if ($dropdown.is(":visible")) {
      $dropdown.hide();
      return;
    }

    populate_propose_user_dropdown();

    const containerEl = $("#propose-invite-users-container")[0];
    if (!containerEl) { return; }

    const rect = containerEl.getBoundingClientRect();
    const dropdownEl = $dropdown[0];

    if (!dropdownEl) { return; }

    $dropdown.show();
    const dropdownHeight = dropdownEl.offsetHeight;
    $dropdown.css({
      top: rect.top - dropdownHeight - 4,
      left: rect.left,
      width: rect.width,
    });
  });

  // dates picker — multi-date, no time
  $(document).on("click.propose-pickers", "#propose-meeting-dates", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const $input = $(e.currentTarget);

    let captured_dates: Date[] = [];

    flatpickr.show_flatpickr(
      util.the($input),
      (_selectedDates) => {
        const isoList = captured_dates.map((d) => {
          const y = d.getFullYear();
          const mo = String(d.getMonth() + 1).padStart(2, "0");
          const dy = String(d.getDate()).padStart(2, "0");
          return `${y}-${mo}-${dy}`;
        });

        $("#propose-meeting-dates-value").val(isoList.join(",")).trigger("input");

        const formatted = captured_dates.map((d) => {
          const dayOfWeek = d.toLocaleDateString("en-US", { weekday: "short" });
          const month = d.toLocaleDateString("en-US", { month: "long" });
          const day = d.getDate();
          return `${dayOfWeek}, ${month} ${day}${ordinal(day)}`;
        }).join("; ");

        $input.val(formatted);
        validate_propose_form();
      },
      new Date(),
      {
        mode: "multiple",
        enableTime: false,
        minDate: new Date(),
        appendTo: document.body,
        dateFormat: "Y-m-d",
        onChange(selectedDates: Date[]) {
          captured_dates = [...selectedDates];
        },
      } as any,
    );
  });

  // times picker — bind directly on the element, not delegated
  const timesInputEl = document.getElementById("propose-meeting-times");
  if (timesInputEl) {
    timesInputEl.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();

      try {
        $(".propose-time-picker").remove();

        const $input = $("#propose-meeting-times");
        const existing = (($("#propose-meeting-times-value").val() ?? "") as string)
          .split(",").map((s) => s.trim()).filter(Boolean);
        const selected = new Set(existing);

        const slots: string[] = [];
        for (let h = 0; h < 24; h++) {
          for (const m of [0, 15, 30, 45]) {
            slots.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
          }
        }

        function format_display(iso: string): string {
          const [hStr, mStr] = iso.split(":");
          const h = Number(hStr);
          const ampm = h < 12 ? "AM" : "PM";
          const h12 = h % 12 === 0 ? 12 : h % 12;
          return `${h12}:${String(Number(mStr)).padStart(2, "0")} ${ampm}`;
        }

        function commit(): void {
          const sorted = [...selected].sort();
          $("#propose-meeting-times-value").val(sorted.join(",")).trigger("input");
          $input.val(sorted.map(format_display).join(", "));
          validate_propose_form();
        }

        const pickerEl = document.createElement("div");
        pickerEl.className = "propose-time-picker";
        Object.assign(pickerEl.style, {
          position: "fixed",
          zIndex: "99999",
          background: "var(--color-background-modal, #fff)",
          border: "1px solid var(--color-border, #ddd)",
          boxShadow: "0 3px 13px rgba(0,0,0,0.08)",
          borderRadius: "5px",
          padding: "8px",
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "2px",
          maxHeight: "260px",
          overflowY: "auto",
          width: "260px",
          pointerEvents: "all",
        });

        for (const slot of slots) {
          const cell = document.createElement("div");
          cell.className = "propose-time-cell" + (selected.has(slot) ? " selected" : "");
          cell.textContent = format_display(slot);
          Object.assign(cell.style, {
            fontSize: "12px",
            padding: "5px 3px",
            textAlign: "center",
            cursor: "pointer",
            borderRadius: "4px",
            lineHeight: "1.3",
            color: "var(--color-text-default)",
            transition: "background 0.1s",
          });
          cell.addEventListener("mouseenter", () => {
            if (!selected.has(slot)) {
              cell.style.background = "var(--color-background-hover, rgba(255,255,255,0.08))";
            }
          });
          cell.addEventListener("mouseleave", () => {
            if (!selected.has(slot)) {
              cell.style.background = "";
            }
          });
          cell.addEventListener("click", (ev) => {
            ev.stopPropagation();
            if (selected.has(slot)) {
              selected.delete(slot);
              cell.classList.remove("selected");
              cell.style.background = "";
              cell.style.color = "var(--color-text-default)";
              cell.style.fontWeight = "";
            } else {
              selected.add(slot);
              cell.classList.add("selected");
              cell.style.background = "var(--color-compose-send-button-background, #6c6cdc)";
              cell.style.color = "#fff";
              cell.style.fontWeight = "500";
            }
            commit();
          });

          if (selected.has(slot)) {
            cell.style.background = "var(--color-compose-send-button-background, #6c6cdc)";
            cell.style.color = "#fff";
            cell.style.fontWeight = "500";
          }
          pickerEl.appendChild(cell);
        }

        const rect = timesInputEl.getBoundingClientRect();
        pickerEl.style.top = `${rect.bottom + 4}px`;
        pickerEl.style.left = `${rect.left}px`;
        document.body.appendChild(pickerEl);

        setTimeout(() => {
          const cells = pickerEl.querySelectorAll(".propose-time-cell");
          const eightAm = cells[32];
          if (eightAm) {
            pickerEl.scrollTop = (eightAm as HTMLElement).offsetTop - 10;
          }

          document.addEventListener("click", function dismiss() {
            pickerEl.remove();
            document.removeEventListener("click", dismiss);
          });
        }, 0);

        pickerEl.addEventListener("click", (ev) => ev.stopPropagation());

      } catch (err) {
        console.error("Time picker error:", err);
      }
    }, true);
  }

  // rsvp deadline picker
  $(document).on("click.propose-pickers", "#propose-rsvp-by", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const $input = $(e.currentTarget);

    const defaultDate = ((): Date => {
      const cur = $<HTMLInputElement>("#propose-rsvp-by-value").val() as string | undefined;
      if (cur) {
        const parsed = new Date(cur);
        if (!Number.isNaN(parsed.getTime())) return parsed;
      }
      return new Date();
    })();

    flatpickr.show_flatpickr(
      util.the($input),
      (selectedDate) => {
        const dt = new Date(selectedDate);
        const isoValue = dt.toISOString();

        $input.val(timerender.get_full_datetime(dt, "time"));
        $("#propose-rsvp-by-value").val(isoValue).trigger("input");
        validate_propose_form();
      },
      defaultDate,
      {
        enableTime: true,
        minDate: new Date(),
        appendTo: document.body,
        onOpen(_selectedDates: Date[], _dateStr: string, instance: any) {
          const inputEl = util.the($input);
          const rect = inputEl.getBoundingClientRect();
          const cal = instance.calendarContainer;
          cal.classList.remove("arrowTop", "arrowBottom", "arrowLeft", "arrowRight");
          cal.style.position = "fixed";
          cal.style.transform = "none";
          cal.style.zIndex = "6000";
          setTimeout(() => {
            const spacing = 8;
            let left = rect.right + spacing;
            let top = rect.top;
            if (left + cal.offsetWidth > window.innerWidth - spacing) {
              left = rect.left - cal.offsetWidth - spacing;
            }
            if (top + cal.offsetHeight > window.innerHeight - spacing) {
              top = window.innerHeight - cal.offsetHeight - spacing;
            }
            if (top < spacing) top = spacing;
            cal.style.left = `${left}px`;
            cal.style.top = `${top}px`;
          }, 0);
        },
      },
    );
  });
}

function on_add_all_users_click(): void {
  if (!invite_users_widget) {
    return;
  }

  const already_added_ids = new Set(user_pill.get_user_ids(invite_users_widget));
  const stream_id = narrow_state.stream_id();

  const candidate_ids: number[] = stream_id !== undefined
    ? [...peer_data.get_subscriber_ids_assert_loaded(stream_id)]
    : people.get_realm_users().map((u) => u.user_id);

  for (const id of candidate_ids) {
    if (already_added_ids.has(id)) {
      continue;
    }
    const user = people.get_by_user_id(id);
    if (user && !user.is_bot) {
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
      modal_title_html: $t_html({ defaultMessage: "Meeting RSVP" }),
      modal_content_html: render_add_rsvp_meeting_modal({}),
      modal_submit_button_text: $t({ defaultMessage: "Submit" }),
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
    launch_propose_meeting_modal();
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

function update_rsvp_channel_warning(): void {
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

function update_propose_channel_warning(): void {
  const stream_id = narrow_state.stream_id();
  const $warning = $("#propose-channel-warning");
  const $checkbox = $<HTMLInputElement>("#propose-create-channel");

  if (!stream_id) {
    $warning.hide();
    $checkbox.prop("checked", false).prop("disabled", false);
    return;
  }

  const subscriber_ids = new Set(peer_data.get_subscriber_ids_assert_loaded(stream_id));
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

export function launch_propose_meeting_modal(): void {
  dialog_widget.launch({
    modal_title_html: $t_html({ defaultMessage: "Propose a Meeting" }),
    modal_content_html: render_add_propose_meeting_modal({}),
    modal_submit_button_text: $t({ defaultMessage: "Submit" }),
    id: "add-propose-meeting-modal",
    form_id: "propose-meeting-form",
    update_submit_disabled_state_on_change: true,
    on_click: submit_propose_meeting_form,
    on_shown: () => $("#propose-meeting-topic").trigger("focus"),
    post_render: propose_meeting_modal_post_render,
    on_hide() {
      $("#propose-user-dropdown").hide();
      $(document).off("click.propose-dropdown");
      $(".propose-time-picker").remove();
    },
  });
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return s[(v - 20) % 10] ?? s[v] ?? s[0]!;
}

export const __test_only = {
    set_invite_users_widget: (w: any) => {
        invite_users_widget = w;
    },
    on_add_all_users_click,
    update_rsvp_submit_button_state,
    reset_composebox_widget_flag: () => {
        composebox_add_meeting_dropdown_widget = false;
    },
    get_composebox_widget_flag: () => composebox_add_meeting_dropdown_widget,
};
