import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_inbox_row from "./inbox_row.ts";

export default function render_inbox_stream_container(context) {
    const out = to_array(context.topics_dict).map(
        (key_value_list) => html`
            <div id="${key_value_list[0]}">
                ${to_array(context.streams_dict).map((stream_key_value) =>
                    stream_key_value[0] === key_value_list[0]
                        ? html` ${{__html: render_inbox_row(stream_key_value[1])}}`
                        : "",
                )}
                <div class="inbox-topic-container">
                    ${to_array(key_value_list[1]).map(
                        (context2) => html` ${{__html: render_inbox_row(context2[1])}}`,
                    )}
                </div>
            </div>
        `,
    );
    return to_html(out);
}
