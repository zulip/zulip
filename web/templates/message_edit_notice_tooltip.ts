import {tooltip_hotkey_hints} from "../src/common.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_edit_notice_tooltip(context) {
    const out = html`<div>
            ${to_bool(context.edit_history_access)
                ? to_bool(context.edited)
                    ? to_bool(context.moved)
                        ? html` <div>${$t({defaultMessage: "View edit and move history"})}</div> `
                        : html` <div>${$t({defaultMessage: "View edit history"})}</div> `
                    : to_bool(context.moved)
                      ? html` <div>${$t({defaultMessage: "View move history"})}</div> `
                      : ""
                : to_bool(context.message_moved_and_move_history_access)
                  ? html` <div>${$t({defaultMessage: "View move history"})}</div> `
                  : ""}${to_bool(context.edited)
                ? html`
                      <div class="tooltip-inner-content italic">
                          ${$t(
                              {defaultMessage: "Last edited {edited_time_string}."},
                              {edited_time_string: context.edited_time_string},
                          )}
                      </div>
                  `
                : ""}${to_bool(context.moved)
                ? html`
                      <div class="tooltip-inner-content italic">
                          ${$t(
                              {defaultMessage: "Last moved {moved_time_string}."},
                              {moved_time_string: context.moved_time_string},
                          )}
                      </div>
                  `
                : ""}
        </div>
        ${to_bool(context.edit_history_access)
            ? html`${tooltip_hotkey_hints("Shift", "H")} `
            : to_bool(context.message_moved_and_move_history_access)
              ? html`${tooltip_hotkey_hints("Shift", "H")} `
              : ""}`;
    return to_html(out);
}
