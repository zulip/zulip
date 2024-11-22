import {html, to_html} from "../shared/src/html.ts";

export default function render_streams_subheader(context) {
    const out = html`<div class="streams_subheader">
        <span class="streams-subheader-wrapper">
            <span class="streams-subheader-name"> ${context.subheader_name} </span>
        </span>
    </div> `;
    return to_html(out);
}
