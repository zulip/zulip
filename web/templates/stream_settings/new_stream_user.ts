import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_new_stream_user(context) {
    const out = html`<tr class="settings-subscriber-row" data-user-id="${context.user_id}">
        <td class="panel_user_list">
            ${{
                __html: render_user_display_only_pill({
                    is_bot: context.is_bot,
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
        <td class="action-column">
            ${to_bool(context.soft_removed)
                ? html` ${{
                      __html: render_action_button({
                          ["aria-label"]: $t({defaultMessage: "Add"}),
                          intent: "neutral",
                          attention: "quiet",
                          label: $t({defaultMessage: "Add"}),
                          custom_classes: "undo_soft_removed_potential_subscriber",
                      }),
                  }}`
                : html` ${{
                      __html: render_action_button({
                          ["aria-label"]: $t({defaultMessage: "Remove"}),
                          intent: "neutral",
                          attention: "quiet",
                          label: $t({defaultMessage: "Remove"}),
                          custom_classes: "remove_potential_subscriber",
                      }),
                  }}`}
        </td>
    </tr> `;
    return to_html(out);
}
