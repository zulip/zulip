import {html, to_html} from "../shared/src/html.ts";
import {tooltip_hotkey_hints} from "../src/common.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_narrow_to_compose_recipients_tooltip(context) {
    const out = html`<div>
            <div>${$t({defaultMessage: "Go to conversation"})}</div>
            ${to_bool(context.display_current_view)
                ? html`
                      <div class="tooltip-inner-content italic">
                          ${context.display_current_view}
                      </div>
                  `
                : ""}
        </div>
        ${tooltip_hotkey_hints("Ctrl", ".")} `;
    return to_html(out);
}
