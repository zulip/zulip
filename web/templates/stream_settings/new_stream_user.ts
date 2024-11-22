import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_new_stream_user(context) {
    const out = html`<tr>
        <td class="panel_user_list">
            ${{
                __html: render_user_display_only_pill({
                    is_active: true,
                    strikethrough: context.soft_removed,
                    display_value: context.full_name,
                    ...context,
                }),
            }}
        </td>
        ${to_bool(context.email)
            ? html`
                  <td
                      class="subscriber-email settings-email-column ${to_bool(context.soft_removed)
                          ? " strikethrough "
                          : ""}"
                  >
                      ${context.email}
                  </td>
              `
            : html`
                  <td
                      class="hidden-subscriber-email ${to_bool(context.soft_removed)
                          ? " strikethrough "
                          : ""}"
                  >
                      ${$t({defaultMessage: "(hidden)"})}
                  </td>
              `}
        <td>
            ${to_bool(context.soft_removed)
                ? html`
                      <button
                          data-user-id="${context.user_id}"
                          class="undo_soft_removed_potential_subscriber button small rounded white"
                      >
                          ${$t({defaultMessage: "Add"})}
                      </button>
                  `
                : html`
                      <button
                          ${to_bool(context.disabled) ? html` disabled="disabled"` : ""}
                          data-user-id="${context.user_id}"
                          class="remove_potential_subscriber button small rounded white"
                      >
                          ${$t({defaultMessage: "Remove"})}
                      </button>
                  `}
        </td>
    </tr> `;
    return to_html(out);
}
