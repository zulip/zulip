import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_group_display_only_pill from "../user_group_display_only_pill.ts";

export default function render_new_user_group_subgroup(context) {
    const out = html`<tr>
        <td class="panel_user_list" colspan="2">
            ${{
                __html: render_user_group_display_only_pill({
                    strikethrough: context.soft_removed,
                    ...context,
                }),
            }}
        </td>
        <td>
            ${to_bool(context.soft_removed)
                ? html`
                      <button
                          data-group-id="${context.group_id}"
                          class="undo_soft_removed_potential_subgroup button small rounded white"
                      >
                          ${$t({defaultMessage: "Add"})}
                      </button>
                  `
                : html`
                      <button
                          data-group-id="${context.group_id}"
                          class="remove_potential_subgroup button small rounded white"
                      >
                          ${$t({defaultMessage: "Remove"})}
                      </button>
                  `}
        </td>
    </tr> `;
    return to_html(out);
}
