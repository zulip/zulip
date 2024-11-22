import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_group_display_only_pill from "../user_group_display_only_pill.ts";

export default function render_user_group_subgroup_entry(context) {
    const out = html`<tr data-subgroup-id="${context.group_id}">
        <td class="subgroup-name panel_user_list" colspan="2">
            ${{__html: render_user_group_display_only_pill(context)}}
        </td>
        ${to_bool(context.can_edit)
            ? html`
                  <td class="remove">
                      <div class="subgroup_list_remove">
                          <form class="remove-subgroup-form">
                              <button
                                  type="submit"
                                  name="remove"
                                  class="remove-subgroup-button button small rounded button-danger"
                              >
                                  ${$t({defaultMessage: "Remove"})}
                              </button>
                          </form>
                      </div>
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
