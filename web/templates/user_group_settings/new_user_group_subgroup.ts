import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_user_group_display_only_pill from "../user_group_display_only_pill.ts";

export default function render_new_user_group_subgroup(context) {
    const out = html`<tr class="user-group-subgroup-row" data-group-id="${context.group_id}">
        <td class="panel_user_list">
            ${{
                __html: render_user_group_display_only_pill({
                    strikethrough: context.soft_removed,
                    ...context,
                }),
            }}
        </td>
        <td class="empty-email-col-for-user-group"></td>
        <td class="action-column">
            ${to_bool(context.soft_removed)
                ? html` ${{
                      __html: render_action_button({
                          ["aria-label"]: $t({defaultMessage: "Add"}),
                          intent: "neutral",
                          attention: "quiet",
                          label: $t({defaultMessage: "Add"}),
                          custom_classes: "undo_soft_removed_potential_subgroup",
                      }),
                  }}`
                : html` ${{
                      __html: render_action_button({
                          ["aria-label"]: $t({defaultMessage: "Remove"}),
                          intent: "neutral",
                          attention: "quiet",
                          label: $t({defaultMessage: "Remove"}),
                          custom_classes: "remove_potential_subgroup",
                      }),
                  }}`}
        </td>
    </tr> `;
    return to_html(out);
}
