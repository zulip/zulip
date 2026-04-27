import $ from "jquery";

import render_availability_submission_modal from "../templates/user_availability_meeting_modal.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import {
  MeetingAvailabilityData,
  type AvailabilityEvent,
} from "./meeting_availability_data.ts";
import * as modals from "./modals.ts";

let current_availability_data: MeetingAvailabilityData | undefined;
let current_callback: ((event: AvailabilityEvent) => void) | undefined;
let selected_slots: Set<string> = new Set();
let is_dragging = false;
let drag_selecting = true; // true = selecting, false = deselecting

function render_grid(): void {
  if (!current_availability_data) {
    return;
  }

  const widget_data = current_availability_data.get_widget_data();
  const dates = widget_data.dates;
  const all_slots = widget_data.all_slots;
  const slot_counts = widget_data.slot_counts;
  const total_respondents = widget_data.total_respondents;
  const slots_per_date = all_slots.length / dates.length;

  //Build time labels from first date's slots
  const time_labels: string[] = [];

  for (let i = 0; i < slots_per_date; i++) {
    const slot = all_slots[i]!;
    const time_part = slot.split("T")[1]!;
    const [hh, mm] = time_part.split(":").map(Number);
    const d = new Date(2000, 0, 1, hh, mm);
    time_labels.push(
      d.toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit"}),
    );
  }

  //Build data headers
  const date_headers = dates
    .map((d) => {
      const dt = new Date(d + "T00:00:00");
      const label = dt.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
      return `<div class="availability-col-header">${label}</div>`;
    })
    .join("");

  //Build rows
  const rows = time_labels
    .map((time_label, row_idx) => {
      const cells = dates
        .map((_date, col_idx) => {
          const slot_key = all_slots[col_idx * slots_per_date + row_idx]!;
          const is_selected = selected_slots.has(slot_key);
          const count = slot_counts[slot_key] ?? 0;
          const intensity =
            total_respondents > 0
              ? Math.round((count / total_respondents) * 4)
              : 0;

          return `<div
                        class="availability-cell ${is_selected ? "availability-cell-selected" : ""} availability-intensity-${intensity}"
                        data-slot="${slot_key}"
                    ></div>`;
        })
        .join("");

      return `
            <div class="availability-row">
                <div class="availability-time-label">${time_label}</div>
                ${cells}
            </div>`;
    })
    .join("");

  const grid_html = `
        <div class="availability-grid-inner">
            <div class="availability-header-row">
                <div class="availability-time-label-empty"></div>
                ${date_headers}
            </div>
            ${rows}
        </div>`;

  $("#availability-grid").html(grid_html);
  bind_grid_events();
}

function bind_grid_events(): void {
  const $grid = $("#availability-grid");

  // Remove any existing handlers first to prevent stacking
  $grid.off("mousedown mouseenter");

  $grid.on("mousedown", ".availability-cell", function (e) {
    e.preventDefault();
    e.stopPropagation();
    is_dragging = true;
    const slot = $(this).data("slot") as string;
    // If clicking a selected cell, drag will deselect; otherwise select
    drag_selecting = !selected_slots.has(slot);
    toggle_slot(slot);
  });

  $grid.on("mouseenter", ".availability-cell", function () {
    if (!is_dragging) {
      return;
    }
    const slot = $(this).data("slot") as string;
    if (drag_selecting) {
      selected_slots.add(slot);
      $(this).addClass("availability-cell-selected");
    } else {
      selected_slots.delete(slot);
      $(this).removeClass("availability-cell-selected");
    }
  });
}

function toggle_slot(slot: string): void {
  if (selected_slots.has(slot)) {
    selected_slots.delete(slot);
  } else {
    selected_slots.add(slot);
  }
  $(`[data-slot="${slot}"]`).toggleClass(
    "availability-cell-selected",
    selected_slots.has(slot),
  );
}

function submit_availability(): void {
  if (!current_availability_data || !current_callback) {
    return;
  }
  const event = current_availability_data.availability_event([
    ...selected_slots,
  ]);
  current_availability_data.handle_availability_event(
    current_availability_data.me,
    event,
  );
  current_callback(event);
  modals.close_active();
}

export function open_availability_modal(
  availability_data: MeetingAvailabilityData,
  callback: (event: AvailabilityEvent) => void,
): void {
  current_availability_data = availability_data;
  current_callback = callback;
  // Pre-populate with user's previous selections if any
  selected_slots = new Set(availability_data.get_my_selected_slots());

  dialog_widget.launch({
    modal_title_html: $t_html({defaultMessage: "Select Your Availability"}),
    modal_content_html: render_availability_submission_modal({}),
    modal_submit_button_text: $t({defaultMessage: "Submit"}),
    id: "availability-submission-modal",
    form_id: "availability-submission-form",
    on_click: submit_availability,
    on_shown() {
      // Show timezone
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const offset = new Date()
        .toLocaleTimeString("en-US", {
          timeZoneName: "short",
        })
        .split(" ")
        .pop();
      $("#availability-timezone-name").text(`${offset}, ${tz}`);
      render_grid();
    },
    on_hide() {
      $(document).off("mouseup.availability-grid");
      current_availability_data = undefined;
      current_callback = undefined;
      selected_slots = new Set();
    },
  });
}
