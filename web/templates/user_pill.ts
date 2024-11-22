import {html, to_html} from "../shared/src/html.ts";
import render_input_pill from "./input_pill.ts";

export default function render_user_pill(context) {
    const out = html`<span class="user-pill pill-container pill-container-button">
        ${{__html: render_input_pill(context.user_pill_context)}}</span
    > `;
    return to_html(out);
}
