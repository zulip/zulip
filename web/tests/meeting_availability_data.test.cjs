"use strict";

const assert = require("node:assert/strict");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {
  generate_slots,
  MeetingAvailabilityData,
  availability_event_schema,
  availability_widget_extra_data_schema,
} = zrequire("meeting_availability_data");

//generate_slots
run_test("generate_slots returns correct slot keys for single date", () => {
  const slots = generate_slots(["2026-04-07"], "09:00", "10:00", 30);
  assert.deepEqual(slots, ["2026-04-07T09:00", "2026-04-07T09:30"]);
});

run_test("generate_slots returns correct slots for multiple dates", () => {
  const slots = generate_slots(
    ["2026-04-07", "2026-04-08"],
    "09:00",
    "10:00",
    30,
  );
  assert.deepEqual(slots, [
    "2026-04-07T09:00",
    "2026-04-07T09:30",
    "2026-04-08T09:00",
    "2026-04-08T09:30",
  ]);
});

run_test("generate_slots respects slot_duration_mins", () => {
  const slots = generate_slots(["2026-04-07"], "09:00", "10:00", 60);
  assert.deepEqual(slots, ["2026-04-07T09:00"]);
});

run_test("generate_slots pads hours and minutes correctly", () => {
  const slots = generate_slots(["2026-04-07"], "09:00", "09:05", 5);
  assert.equal(slots[0], "2026-04-07T09:00");
});

run_test("generate_slots returns empty for zero-length range", () => {
  const slots = generate_slots(["2026-04-07"], "09:00", "09:00", 30);
  assert.deepEqual(slots, []);
});

run_test("generate_slots returns empty for empty dates", () => {
  const slots = generate_slots([], "09:00", "10:00", 30);
  assert.deepEqual(slots, []);
});

// availability widget extra data schema
run_test("availability_widget_extra_data_schema accepts valid data", () => {
  const result = availability_widget_extra_data_schema.safeParse({
    topic: "Team sync",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "17:00",
    slot_duration_mins: 30,
    invitees: [1, 2],
  });
  assert.ok(result.success);
});

run_test("availability_widget_extra_data_schema rejects missing topic", () => {
  const result = availability_widget_extra_data_schema.safeParse({
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "17:00",
    slot_duration_mins: 30,
    invitees: [],
  });
  assert.ok(!result.success);
});

run_test(
  "availability_widget_extra_data_schema rejects non-number invitees",
  () => {
    const result = availability_widget_extra_data_schema.safeParse({
      topic: "Team sync",
      dates: ["2026-04-07"],
      start_time: "09:00",
      end_time: "17:00",
      slot_duration_mins: 30,
      invitees: ["alice"],
    });
    assert.ok(!result.success);
  },
);

// availability_event_schema
run_test("availability_event_schema accepts valid event", () => {
  const result = availability_event_schema.safeParse({
    type: "availability",
    available_slots: ["2026-04-07T09:00", "2026-04-07T09:30"],
  });
  assert.ok(result.success);
  assert.deepEqual(result.data.available_slots, [
    "2026-04-07T09:00",
    "2026-04-07T09:30",
  ]);
});

run_test("availability_event_schema rejects wrong type", () => {
  const result = availability_event_schema.safeParse({
    type: "vote",
    available_slots: [],
  });
  assert.ok(!result.success);
});

run_test("availability_event_schema accepts empty slots", () => {
  const result = availability_event_schema.safeParse({
    type: "availability",
    available_slots: [],
  });
  assert.ok(result.success);
});

// MeetingAvailabilityData constructor
run_test("MeetingAvailabilityData constructor stores all fields", () => {
  const data = new MeetingAvailabilityData({
    topic: "Team sync",
    dates: ["2026-04-07", "2026-04-08"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1, 2],
    current_user_id: 99,
  });
  assert.equal(data.topic, "Team sync");
  assert.deepEqual(data.dates, ["2026-04-07", "2026-04-08"]);
  assert.equal(data.start_time, "09:00");
  assert.equal(data.end_time, "10:00");
  assert.equal(data.slot_duration_mins, 30);
  assert.deepEqual(data.invitees, [1, 2]);
  assert.equal(data.me, 99);
  assert.equal(data.responses.size, 0);
});

// availability_event
run_test("availability_event returns correct shape", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 1,
  });
  assert.deepEqual(data.availability_event(["2026-04-07T09:00"]), {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
});

run_test("availability_event returns empty slots", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 1,
  });
  assert.deepEqual(data.availability_event([]), {
    type: "availability",
    available_slots: [],
  });
});

//handle availability event
run_test("handle_availability_event records slots for a user", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [10],
    current_user_id: 99,
  });
  data.handle_availability_event(10, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  assert.ok(data.responses.get(10)?.has("2026-04-07T09:00"));
});

run_test("handle_availability_event overwrites previous response", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [10],
    current_user_id: 99,
  });
  data.handle_availability_event(10, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  data.handle_availability_event(10, {
    type: "availability",
    available_slots: ["2026-04-07T09:30"],
  });
  assert.ok(!data.responses.get(10)?.has("2026-04-07T09:00"));
  assert.ok(data.responses.get(10)?.has("2026-04-07T09:30"));
});

//get slot count
run_test("get_slot_count returns 0 with no responses", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 99,
  });
  assert.equal(data.get_slot_count("2026-04-07T09:00"), 0);
});

run_test("get_slot_count counts correctly across multiple users", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1, 2, 3],
    current_user_id: 99,
  });
  data.handle_availability_event(1, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  data.handle_availability_event(2, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  data.handle_availability_event(3, {
    type: "availability",
    available_slots: ["2026-04-07T09:30"],
  });
  assert.equal(data.get_slot_count("2026-04-07T09:00"), 2);
  assert.equal(data.get_slot_count("2026-04-07T09:30"), 1);
});

//get my selected slots
run_test("get_my_selected_slots returns empty set initially", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 99,
  });
  assert.equal(data.get_my_selected_slots().size, 0);
});

run_test("get_my_selected_slots returns current user slots", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 99,
  });
  data.handle_availability_event(99, {
    type: "availability",
    available_slots: ["2026-04-07T09:00", "2026-04-07T09:30"],
  });
  assert.ok(data.get_my_selected_slots().has("2026-04-07T09:00"));
  assert.ok(data.get_my_selected_slots().has("2026-04-07T09:30"));
});

//get total respondents
run_test("get_total_respondents returns 0 initially", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 99,
  });
  assert.equal(data.get_total_respondents(), 0);
});

run_test("get_total_respondents counts unique users", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1, 2],
    current_user_id: 99,
  });
  data.handle_availability_event(1, {
    type: "availability",
    available_slots: [],
  });
  data.handle_availability_event(2, {
    type: "availability",
    available_slots: [],
  });
  data.handle_availability_event(1, {
    type: "availability",
    available_slots: [],
  }); // overwrite
  assert.equal(data.get_total_respondents(), 2);
});

//get widget data
run_test("get_widget_data returns correct all_slots", () => {
  const data = new MeetingAvailabilityData({
    topic: "Team sync",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1],
    current_user_id: 99,
  });
  const widget_data = data.get_widget_data();
  assert.deepEqual(widget_data.all_slots, [
    "2026-04-07T09:00",
    "2026-04-07T09:30",
  ]);
});

run_test("get_widget_data returns correct slot_counts", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1],
    current_user_id: 99,
  });
  data.handle_availability_event(1, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  const {slot_counts} = data.get_widget_data();
  assert.equal(slot_counts["2026-04-07T09:00"], 1);
  assert.equal(slot_counts["2026-04-07T09:30"], 0);
});

run_test("get_widget_data returns correct total_respondents", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [1, 2],
    current_user_id: 99,
  });
  data.handle_availability_event(1, {
    type: "availability",
    available_slots: [],
  });
  data.handle_availability_event(2, {
    type: "availability",
    available_slots: [],
  });
  assert.equal(data.get_widget_data().total_respondents, 2);
});

run_test("get_widget_data my_selected_slots reflects current user", () => {
  const data = new MeetingAvailabilityData({
    topic: "x",
    dates: ["2026-04-07"],
    start_time: "09:00",
    end_time: "10:00",
    slot_duration_mins: 30,
    invitees: [],
    current_user_id: 99,
  });
  data.handle_availability_event(99, {
    type: "availability",
    available_slots: ["2026-04-07T09:00"],
  });
  assert.ok(data.get_widget_data().my_selected_slots.has("2026-04-07T09:00"));
});
