import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_admin_user_list(context) {
    const out = html`<tr
        class="user_row${to_bool(context.is_active) ? " active-user" : " deactivated_user"}"
        data-user-id="${context.user_id}"
    >
        <td class="user_name panel_user_list">
            ${{
                __html: render_user_display_only_pill({
                    img_src: context.img_src,
                    user_id: context.user_id,
                    display_value: context.full_name,
                }),
            }}
        </td>
        ${to_bool(context.display_email)
            ? html`
                  <td class="email settings-email-column">
                      <span class="email">${context.display_email}</span>
                  </td>
              `
            : html`
                  <td class="email settings-email-column">
                      <span class="hidden-email">${$t({defaultMessage: "(hidden)"})}</span>
                  </td>
              `}
        <td>
            <span class="user_role">${context.user_role_text}</span>
        </td>
        ${to_bool(context.is_bot)
            ? html`
                  <td>
                      <span class="owner panel_user_list">
                          ${to_bool(context.no_owner)
                              ? html` ${context.bot_owner_full_name} `
                              : html` ${{
                                    __html: render_user_display_only_pill({
                                        is_active: context.is_bot_owner_active,
                                        img_src: context.owner_img_src,
                                        user_id: context.bot_owner_id,
                                        display_value: context.bot_owner_full_name,
                                    }),
                                }}`}
                      </span>
                  </td>
                  <td class="bot_type">
                      <span class="bot type">${context.bot_type}</span>
                  </td>
              `
            : to_bool(context.display_last_active_column)
              ? html` <td class="last_active">${context.last_active_date}</td> `
              : ""}${to_bool(context.can_modify)
            ? html`
                  <td class="actions">
                      <span class="user-status-settings">
                          <span
                              ${to_bool(context.is_bot) && to_bool(context.cannot_edit)
                                  ? html`class="tippy-zulip-tooltip"`
                                  : ""}
                              ${to_bool(context.is_bot) && to_bool(context.cannot_edit)
                                  ? html`data-tippy-content="${$t({
                                        defaultMessage: "This bot cannot be edited.",
                                    })}"`
                                  : ""}
                          >
                              <button
                                  class="button rounded small button-warning open-user-form tippy-zulip-delayed-tooltip"
                                  data-tippy-content="${to_bool(context.is_bot)
                                      ? !to_bool(context.cannot_edit)
                                          ? $t({defaultMessage: "Edit bot"})
                                          : ""
                                      : $t({defaultMessage: "Edit user"})}"
                                  data-user-id="${context.user_id}"
                                  ${to_bool(context.cannot_edit) ? html`disabled="disabled"` : ""}
                              >
                                  <i class="fa fa-pencil" aria-hidden="true"></i>
                              </button>
                          </span>
                          ${to_bool(context.is_active)
                              ? html`
                                    <span
                                        ${to_bool(context.is_bot) &&
                                        to_bool(context.cannot_deactivate)
                                            ? html`class="tippy-zulip-tooltip"`
                                            : ""}
                                        ${to_bool(context.is_bot) &&
                                        to_bool(context.cannot_deactivate)
                                            ? html`data-tippy-content="${$t({
                                                  defaultMessage: "This bot cannot be deactivated.",
                                              })}"`
                                            : ""}
                                    >
                                        <button
                                            class="button rounded small button-danger ${!(
                                                to_bool(context.is_bot) &&
                                                to_bool(context.cannot_deactivate)
                                            )
                                                ? "deactivate"
                                                : ""}"
                                            ${to_bool(context.cannot_deactivate)
                                                ? html`disabled="disabled"`
                                                : ""}
                                        >
                                            <i class="fa fa-user-times" aria-hidden="true"></i>
                                        </button>
                                    </span>
                                `
                              : html`
                                    <button class="button rounded small reactivate button-warning">
                                        <i class="fa fa-user-plus" aria-hidden="true"></i>
                                    </button>
                                `}
                      </span>
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
