import {tooltip_hotkey_hints} from "../src/common.ts";
import {html, to_html} from "../src/html.ts";

export default function render_narrow_tooltip_list_of_topics(context) {
    const out = html`${context.content} ${tooltip_hotkey_hints("Y")} `;
    return to_html(out);
}
