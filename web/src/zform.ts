import $ from "jquery";
import assert from "minimalistic-assert";

import render_widgets_zform_choices from "../templates/widgets/zform_choices.hbs";

import * as blueslip from "./blueslip.ts";
import type {Message} from "./message_store.ts";
import * as transmit from "./transmit.ts";
import type {Event} from "./widget_data.ts";
import type {AnyWidgetData, WidgetData} from "./widget_schema.ts";
import type {ZFormExtraData} from "./zform_data.ts";

export const widget_type = "zform";

export function activate(opts: {any_data: AnyWidgetData; message: Message}): {
    inbound_events_handler: (events: Event[]) => void;
    widget_data: WidgetData;
} {
    assert(opts.any_data.widget_type === "zform");
    if (opts.any_data.extra_data === null) {
        blueslip.error("invalid zform extra data");
        const widget_data = {
            widget_type: opts.any_data.widget_type,
            data: undefined,
        };
        return {
            inbound_events_handler(_events: Event[]): void {
                /* noop */
            },
            widget_data,
        };
    }
    const data = opts.any_data.extra_data;
    // Assign idx values to each of our choices so that
    // our template can create data-idx values for our
    // JS code to use later.
    const data_with_choices_with_idx = {
        ...data,
        choices: data.choices.map((choice, idx) => ({...choice, idx})),
    };
    const widget_data = {
        widget_type: opts.any_data.widget_type,
        data: data_with_choices_with_idx,
    };

    const handle_events = function (events: Event[]): void {
        if (events) {
            blueslip.info("unexpected");
        }
    };

    return {inbound_events_handler: handle_events, widget_data};
}

export function render(opts: {$elem: JQuery; message: Message; widget_data: WidgetData}): void {
    assert(opts.widget_data.widget_type === "zform");
    const $outer_elem = opts.$elem;
    const data_with_choices_with_idx = opts.widget_data.data;
    if (!data_with_choices_with_idx) {
        return;
    }

    function make_choices(data: ZFormExtraData): JQuery {
        const html = render_widgets_zform_choices(data_with_choices_with_idx);
        const $elem = $(html);

        $elem.find("button").on("click", (e) => {
            e.stopPropagation();

            // Grab our index from the markup.
            const idx = Number.parseInt($(e.target).attr("data-idx")!, 10);

            // Use the index from the markup to dereference our
            // data structure.
            const reply_content = data.choices[idx]!.reply;

            transmit.reply_message(opts.message, reply_content);
        });

        return $elem;
    }

    if (data_with_choices_with_idx.type === "choices") {
        $outer_elem.html(make_choices(data_with_choices_with_idx).html());
    }
    return;
}
