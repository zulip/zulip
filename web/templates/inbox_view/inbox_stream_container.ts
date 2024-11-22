import {html, to_html} from "../../shared/src/html.ts";
import {to_array} from "../../src/hbs_compat.ts";
import render_inbox_row from "./inbox_row.ts";

export default function render_inbox_stream_container(context) {
    const out = to_array(context.topics_dict).map(
        (topics_dict_entry) => html`
            <div id="${topics_dict_entry[0]}">
                ${to_array(context.streams_dict).map((streams_dict_entry) =>
                    streams_dict_entry[0] === topics_dict_entry[0]
                        ? html` ${{__html: render_inbox_row(streams_dict_entry[1])}}`
                        : "",
                )}
                <div class="inbox-topic-container">
                    ${to_array(topics_dict_entry[1]).map(
                        (context2) => html` ${{__html: render_inbox_row(context2[1])}}`,
                    )}
                </div>
            </div>
        `,
    );
    return to_html(out);
}
