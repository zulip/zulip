import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_inbox_row from "./inbox_row.ts";

export default function render_inbox_stream_container(context) {
    const out = to_array(context.topics_dict).map(
        (topics_entry) => html`
            <div id="${topics_entry[0]}">
                ${to_array(context.streams_dict).map((stream_entry) =>
                    stream_entry[0] === topics_entry[0]
                        ? html` ${{__html: render_inbox_row(stream_entry[1])}}`
                        : "",
                )}
                <div class="inbox-topic-container">
                    ${to_array(topics_entry[1]).map(
                        (context2) => html` ${{__html: render_inbox_row(context2[1])}}`,
                    )}
                </div>
            </div>
        `,
    );
    return to_html(out);
}
