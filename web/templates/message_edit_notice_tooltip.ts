import {html, to_html} from "../shared/src/html.ts";
import {tooltip_hotkey_hints} from "../src/common.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_edit_notice_tooltip(context) {
    const out = html`<div>
            ${to_bool(context.realm_allow_edit_history)
                ? html` <div>${$t({defaultMessage: "View edit history"})}</div> `
                : ""}
            <div class="tooltip-inner-content italic">
                ${to_bool(context.moved)
                    ? html`
                          ${$t(
                              {defaultMessage: "Last moved {last_edit_timestr}."},
                              {last_edit_timestr: context.last_edit_timestr},
                          )}
                      `
                    : html`
                          ${$t(
                              {defaultMessage: "Last edited {last_edit_timestr}."},
                              {last_edit_timestr: context.last_edit_timestr},
                          )}
                      `}
            </div>
        </div>
        ${to_bool(context.realm_allow_edit_history)
            ? html`${tooltip_hotkey_hints("Shift", "H")} `
            : ""}`;
    return to_html(out);
}
