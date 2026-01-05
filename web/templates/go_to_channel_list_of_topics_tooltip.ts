import {tooltip_hotkey_hints} from "../src/common.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_go_to_channel_list_of_topics_tooltip() {
    const out = html`<div>${$t({defaultMessage: "Go to list of topics"})}</div>
        ${tooltip_hotkey_hints("Y")} `;
    return to_html(out);
}
