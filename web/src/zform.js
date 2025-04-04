import $ from "jquery";

import render_widgets_zform_choices from "../templates/widgets/zform_choices.hbs";

import * as blueslip from "./blueslip.ts";
import {zform_widget_extra_data_schema} from "./submessage.ts";
import * as transmit from "./transmit.js";

export function activate(opts) {
    const self = {};

    const $outer_elem = opts.$elem;
    const parse_result = zform_widget_extra_data_schema.safeParse(opts.extra_data);

    if (!parse_result.success) {
        blueslip.warn("invalid zform extra data", parse_result.error.issues);
        return undefined;
    }
    const {data} = parse_result;

    function make_choices(data) {
        // Assign idx values to each of our choices so that
        // our template can create data-idx values for our
        // JS code to use later.
        for (const [idx, choice] of data.choices.entries()) {
            choice.idx = idx;
        }

        const html = render_widgets_zform_choices(data);
        const $elem = $(html);

        $elem.find("button").on("click", (e) => {
            e.stopPropagation();

            // Grab our index from the markup.
            const idx = $(e.target).attr("data-idx");

            // Use the index from the markup to dereference our
            // data structure.
            const reply_content = data.choices[idx].reply;

            transmit.reply_message({
                message: opts.message,
                content: reply_content,
            });
        });

        return $elem;
    }

    function render() {
        let rendered_widget;

        if (data.type === "choices") {
            rendered_widget = make_choices(data);
            $outer_elem.html(rendered_widget);
        }
    }

    self.handle_events = function (events) {
        if (events) {
            blueslip.info("unexpected");
        }
        render();
    };

    render();

    return self;
}
