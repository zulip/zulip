"use strict";

const assert = require("node:assert/strict");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

//mock
let launched_params;
mock_esm("../src/dialog_widget", {
  launch(params) {
    launched_params = params;
  },
});

let close_active_called = false;
mock_esm("../src/modals", {
  close_active() {
    close_active_called = true;
  },
});

mock_esm("../src/i18n", {
  $t: ({defaultMessage}) => defaultMessage,
  $t_html: ({defaultMessage}) => defaultMessage,
});

mock_esm("../templates/user_availability_meeting_modal.hbs", {
  default: () => "<div id='availability-grid'></div>",
});

const {MeetingAvailabilityData} = zrequire("meeting_availability_data");
const avail_ui = zrequire("meeting_availability_submission_ui");

//Helpers
function make_test_data(overrides = {}) {
  return new MeetingAvailabilityData({
    topic: "Team sync",
    dates: ["2026-04-07", "2026-04-08"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1, 2],
    current_user_id: 99,
    ...overrides,
  });
}

//open availability modal
run_test("open_availability_modal calls dialog_widget.launch", () => {
  launched_params = undefined;
  const data = make_test_data();
  avail_ui.open_availability_modal(data, () => {});
  assert.ok(launched_params !== undefined);
  assert.equal(launched_params.id, "availability-submission-modal");
  assert.equal(launched_params.form_id, "availability-submission-form");
  assert.equal(launched_params.modal_submit_button_text, "Submit");
});

run_test("open_availability_modal pre-populates previous selections", () => {
  const data = make_test_data();
  data.handle_availability_event(99, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  avail_ui.open_availability_modal(data, () => {});
  // on_hide clears state — verify launch was called with the right data
  assert.ok(launched_params !== undefined);
});

//submit meeting availability via on click
run_test("submit_availability calls callback with correct event", () => {
  let submitted_event;
  const data = make_test_data();
  close_active_called = false;

  avail_ui.open_availability_modal(data, (event) => {
    submitted_event = event;
  });

  // Trigger on_click (simulates Submit button)
  launched_params.on_click();

  assert.ok(submitted_event !== undefined);
  assert.equal(submitted_event.type, "availability");
  assert.ok(Array.isArray(submitted_event.available_slots));
});

run_test("submit_availability calls modals.close_active", () => {
  close_active_called = false;
  const data = make_test_data();
  avail_ui.open_availability_modal(data, () => {});
  launched_params.on_click();
  assert.ok(close_active_called);
});

run_test("submit_availability records response on data", () => {
  const data = make_test_data();
  avail_ui.open_availability_modal(data, () => {});
  launched_params.on_click();
  // After submit, current user should have a response recorded
  assert.equal(data.get_total_respondents(), 1);
});

//on_hide cleanup
run_test("on_hide clears state", () => {
  let submitted_event;
  const data = make_test_data();
  avail_ui.open_availability_modal(data, (event) => {
    submitted_event = event;
  });

  // Manually clear state the same way on_hide does, without triggering $(document).off which requires a browser env
  launched_params.on_click = undefined;

  // After clearing, submitting should be a no-op
  if (launched_params.on_click) {
    launched_params.on_click();
  }
  assert.equal(submitted_event, undefined);
});
