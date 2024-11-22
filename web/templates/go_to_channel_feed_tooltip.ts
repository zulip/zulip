import {html, to_html} from "../shared/src/html.ts";
import {tooltip_hotkey_hints} from "../src/common.ts";
import {$t} from "../src/i18n.ts";

export default function render_go_to_channel_feed_tooltip() {
    const out = html`<div>${$t({defaultMessage: "Go to channel feed"})}</div>
        ${tooltip_hotkey_hints("s")} `;
    return to_html(out);
}
