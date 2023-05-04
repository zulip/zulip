"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const scheduled_messages = zrequire("scheduled_messages");

function get_expected_send_opts(expecteds) {
    const modal_opts = {
        send_later_tomorrow: {
            tomorrow_nine_am: {
                text: "translated: Tomorrow at 9:00 AM",
                time: "9:00 am",
            },
            tomorrow_four_pm: {
                text: "translated: Tomorrow at 4:00 PM",
                time: "4:00 pm",
            },
        },
        send_later_custom: {
            text: "translated: Custom",
        },
        possible_send_later_today: false,
        possible_send_later_monday: false,
    };
    const optional_modal_opts = {
        send_later_today: {
            today_nine_am: {
                text: "translated: Today at 9:00 AM",
                time: "9:00 am",
            },
            today_four_pm: {
                text: "translated: Today at 4:00 PM",
                time: "4:00 pm",
            },
        },
        send_later_monday: {
            monday_nine_am: {
                text: "translated: Monday at 9:00 AM",
                time: "9:00 am",
            },
        },
    };

    // 'today_nine_am'
    // 'today_four_pm'
    // 'monday_nine_am'
    for (const expect of expecteds) {
        const day = expect.split("_")[0]; // "today", "monday"
        if (!modal_opts[`possible_send_later_${day}`]) {
            modal_opts[`possible_send_later_${day}`] = {};
        }
        modal_opts[`possible_send_later_${day}`][expect] =
            optional_modal_opts[`send_later_${day}`][expect];
    }

    return modal_opts;
}

run_test("scheduled_modal_opts", () => {
    // Sunday thru Saturday
    const days = [
        "2023-04-30",
        "2023-05-01",
        "2023-05-02",
        "2023-05-03",
        "2023-05-04",
        "2023-05-05",
        "2023-05-06",
    ];
    // Extra options change based on the hour of day
    const options_by_hour = [
        {hour: "T06:00:00", extras: ["today_nine_am", "today_four_pm"]},
        {hour: "T11:00:00", extras: ["today_four_pm"]},
        {hour: "T17:00:00", extras: []},
    ];

    // Now we can test those hourly options on each day of the week
    for (const day of days) {
        for (const opts of options_by_hour) {
            const date = new Date(day + opts.hour);
            // On Fridays (5) and Saturdays (6), add the Monday option
            if (date.getDay() > 4) {
                opts.extras.push("monday_nine_am");
            }
            const modal_opts = scheduled_messages.get_filtered_send_opts(date);
            const expected_opts = get_expected_send_opts(opts.extras);
            assert.deepEqual(modal_opts, expected_opts);
        }
    }
});

run_test("scheduled_selected_times", () => {
    // When scheduling a message on a Monday at 6:00am
    // that will be sent tomorrow at 4pm
    let date = new Date("2023-05-01T06:00:00");
    let send_at_time = scheduled_messages.get_send_at_time_from_opts(
        "tomorrow_four_pm",
        "send_later_tomorrow",
        date,
    );
    assert.equal(send_at_time, "May 2 2023 4:00 pm");
    // When scheduling a message on a Friday at 5:00pm
    // that will be sent Monday at 9am
    date = new Date("2023-05-05T17:00:00");
    send_at_time = scheduled_messages.get_send_at_time_from_opts(
        "monday_nine_am",
        "send_later_monday",
        date,
    );
    assert.equal(send_at_time, "May 8 2023 9:00 am");
});
