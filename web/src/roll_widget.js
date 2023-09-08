import $ from "jquery";

import { RollData } from "../shared/src/roll_data";
import render_widgets_roll_widget from "../templates/widgets/roll_widget.hbs";

import * as blueslip from "./blueslip";
import * as keydown_util from "./keydown_util";
import * as people from "./people";

export function activate({
    $elem,
    callback,
    extra_data: { count, range = "" } = {},
    message,
}) {
    const is_my_roll = people.is_my_user_id(message.sender_id);
    const roll_data = new RollData({
        message_sender_id: message.sender_id,
        current_user_id: people.my_current_user_id(),
        is_my_roll,
        range,
        count,
        report_error_function: blueslip.warn,
    });

    function render_roll() {
        const count = roll_data.get_count();
        const range = roll_data.get_range();
        const ans = roll_data.get_answer();

        $elem.find(".roll-header").text("Rolling " + count + "dice" + "in range: " + range);
        $elem.find(".roll-subheader").text("Result: [" + ans + "]");

    }

    function submit_roll() {
        const $roll_input = $elem.find("input.roll-question");
        let new_roll = $roll_input.val().trim();
        const old_roll = roll_data.get_roll();

        if (new_roll.trim() === "") {
            new_roll = old_roll;
        }

        roll_data.set_roll(new_roll);
        render_roll();

        // If there were no actual edits, we can exit now.
        if (new_roll === old_roll) {
            return;
        }

        const data = roll_data.handle.question.outbound(new_roll);
        callback(data);
    }

    function build_widget() {
        const html = render_widgets_roll_widget();
        $elem.html(html);

        $elem.find("input.roll-statement").on("keyup", (e) => {
            e.stopPropagation();
            update_edit_controls();
        });

        $elem.find("input.roll-statement").on("keydown", (e) => {
            e.stopPropagation();

            if (keydown_util.is_enter_event(e)) {
                submit_roll();
                return;
            }

            if (e.key === "Escape") {
                abort_edit();
                return;
            }
        });

    }

    function render_results() {
        const widget_data = roll_data.get_widget_data();

        const html = render_widgets_roll_widget_results(widget_data);
        $elem.find("ul.roll-widget").html(html);

    }

    $elem.handle_events = function (events) {
        for (const event of events) {
            roll_data.handle_event(event.sender_id, event.data);
        }

        render_roll();
        render_results();
    };

    build_widget();
    render_roll();
    render_results();
}
