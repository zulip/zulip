import {tooltip_hotkey_hints} from "../src/common.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_drafts_tooltip(context) {
    const out = html`<div>
            <div>${$t({defaultMessage: "View drafts"})}</div>
            ${to_bool(context.draft_count_msg)
                ? html` <div class="tooltip-inner-content italic">${context.draft_count_msg}</div> `
                : ""}
        </div>
        ${tooltip_hotkey_hints("D")} `;
    return to_html(out);
}
