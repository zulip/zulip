import {html, to_html} from "../shared/src/html.ts";
import render_dropdown_widget from "./dropdown_widget.ts";

export default function render_dropdown_widget_wrapper(context) {
    const out = html`<div id="${context.widget_name}_widget_wrapper" tabindex="0">
        ${{__html: render_dropdown_widget({disable_keyboard_focus: "true", ...context})}}
    </div> `;
    return to_html(out);
}
