import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_stream_member_list_entry(context) {
    const out = html`<tr data-subscriber-id="${context.user_id}">
        <td class="subscriber-name panel_user_list">
            ${{
                __html: render_user_display_only_pill({
                    is_active: true,
                    display_value: context.name,
                    ...context,
                }),
            }}
        </td>
        ${to_bool(context.email)
            ? html` <td class="subscriber-email settings-email-column">${context.email}</td> `
            : html`
                  <td class="hidden-subscriber-email">${$t({defaultMessage: "(hidden)"})}</td>
              `}${to_bool(context.can_remove_subscribers)
            ? html`
                  <td class="unsubscribe">
                      <div class="subscriber_list_remove">
                          <form class="remove-subscriber-form">
                              <button
                                  type="submit"
                                  name="unsubscribe"
                                  class="remove-subscriber-button button small rounded button-danger"
                              >
                                  ${to_bool(context.for_user_group_members)
                                      ? html` ${$t({defaultMessage: "Remove"})} `
                                      : html` ${$t({defaultMessage: "Unsubscribe"})} `}
                              </button>
                          </form>
                      </div>
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
