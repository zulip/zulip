import $ from "jquery";

import render_widgets_zform_choices from "../templates/widgets/zform_choices.hbs";

import * as blueslip from "./blueslip.ts";
import type {Message} from "./message_store.ts";
import * as transmit from "./transmit.ts";
import type {ZFormData} from "./zform_data.ts";

// Our Event data from the server is opaque and unknown
// until the widget parses it with zod.
export type Event = {sender_id: number; data: unknown};

export function activate(opts: {
    $elem: JQuery;
    form_data: ZFormData;
    message: Message;
}): (events: Event[]) => void {
    const $outer_elem = opts.$elem;
    const form_data = opts.form_data;

    function make_choices(): JQuery {
        // Assign idx values to each of our choices so that
        // our template can create data-idx values for our
        // JS code to use later.
        const data_with_choices_with_idx = {
            ...form_data,
            choices: form_data.choices.map((choice, idx) => ({...choice, idx})),
        };

        const html = render_widgets_zform_choices(data_with_choices_with_idx);
        const $elem = $(html);

        $elem.find("button").on("click", (e) => {
            e.stopPropagation();

            // Grab our index from the markup.
            const idx = Number.parseInt($(e.target).attr("data-idx")!, 10);

            // Use the index from the markup to dereference our
            // data structure.
            const reply_content = form_data.choices[idx]!.reply;

            transmit.reply_message(opts.message, reply_content);
        });

        return $elem;
    }

    function render(): void {
        if (form_data.type === "choices") {
            $outer_elem.html(make_choices().html());
        }
    }

    const handle_events = function (events: Event[]): void {
        if (events) {
            blueslip.info("unexpected");
        }
        render();
    };

    render();

    return handle_events;
}
