import {html, to_html} from "../shared/src/html.ts";
import {tooltip_hotkey_hints} from "../src/common.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_org_logo_tooltip(context) {
    const out = html`<div>
            <div>${$t({defaultMessage: "Go to home view"})} (${context.home_view})</div>
        </div>
        ${to_bool(context.escape_navigates_to_home_view)
            ? html` ${tooltip_hotkey_hints("Esc")} `
            : html` ${tooltip_hotkey_hints("Ctrl", "[")} `}`;
    return to_html(out);
}
