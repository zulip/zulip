import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";
import render_user_group_display_only_pill from "../user_group_display_only_pill.ts";

export default function render_user_group_subgroup_entry(context) {
    const out = html`<tr data-subgroup-id="${context.group_id}" class="hidden-remove-button-row">
        <td class="subgroup-name panel_user_list">
            ${{__html: render_user_group_display_only_pill(context)}}
        </td>
        <td class="empty-email-col-for-user-group"></td>
        ${to_bool(context.can_remove_members)
            ? html`
                  <td class="remove remove-button-wrapper remove-button-column">
                      ${{
                          __html: render_icon_button({
                              ["data-tippy-content"]: $t({defaultMessage: "Remove"}),
                              ["aria-label"]: $t({defaultMessage: "Remove"}),
                              intent: "danger",
                              custom_classes:
                                  "hidden-remove-button remove-subgroup-button tippy-zulip-delayed-tooltip",
                              icon: "close",
                          }),
                      }}
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
