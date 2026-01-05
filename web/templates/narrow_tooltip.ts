import {tooltip_hotkey_hints} from "../src/common.ts";
import {html, to_html} from "../src/html.ts";

export default function render_narrow_tooltip(context) {
    const out = html`${context.content} ${tooltip_hotkey_hints("S")} `;
    return to_html(out);
}
