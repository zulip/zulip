import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_settings_user_list_row(context) {
    const out = html`<tr
        class="user_row${to_bool(context.is_active) ? " active-user" : " deactivated_user"}"
        data-user-id="${context.user_id}"
    >
        <td class="user_name panel_user_list">
            ${{
                __html: render_user_display_only_pill({
                    is_current_user: context.is_current_user,
                    is_active: context.is_active,
                    img_src: context.img_src,
                    is_bot: context.is_bot,
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
              ? html`
                    <td class="last_active">
                        ${to_bool(context.last_active_date)
                            ? html` ${context.last_active_date} `
                            : html` <div class="loading-placeholder"></div> `}
                    </td>
                `
              : ""}${to_bool(context.is_bot) || to_bool(context.can_modify)
            ? html`
                  <td class="actions">
                      <span class="user-status-settings">
                          ${to_bool(context.is_bot) && to_bool(context.show_download_zuliprc_button)
                              ? html`
                                    <a
                                        type="submit"
                                        download="zuliprc"
                                        data-user-id="${context.user_id}"
                                        class="hidden-zuliprc-download"
                                        hidden
                                    ></a>
                                    <span
                                        class="tippy-zulip-delayed-tooltip"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Download zuliprc",
                                        })}"
                                    >
                                        ${{
                                            __html: render_icon_button({
                                                custom_classes: "download-bot-zuliprc-button",
                                                intent: "neutral",
                                                icon: "download",
                                            }),
                                        }}
                                    </span>
                                `
                              : ""}${to_bool(context.is_bot) &&
                          to_bool(context.show_generate_integration_url_button)
                              ? html`
                                    <span
                                        class="tippy-zulip-delayed-tooltip"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Generate URL for integration",
                                        })}"
                                    >
                                        ${{
                                            __html: render_icon_button({
                                                custom_classes: "generate-integration-url-button",
                                                intent: "neutral",
                                                icon: "link-2",
                                            }),
                                        }}
                                    </span>
                                `
                              : ""}
                          <span
                              class="${to_bool(context.is_bot) && to_bool(context.cannot_edit)
                                  ? "tippy-zulip-tooltip"
                                  : "tippy-zulip-delayed-tooltip"}"
                              ${to_bool(context.is_bot) && to_bool(context.cannot_edit)
                                  ? html`
                                        data-tippy-content="${$t({
                                            defaultMessage: "This bot cannot be managed.",
                                        })}"
                                    `
                                  : html`
                                        data-tippy-content="${to_bool(context.is_bot)
                                            ? !to_bool(context.cannot_edit)
                                                ? $t({defaultMessage: "Manage bot"})
                                                : ""
                                            : $t({defaultMessage: "Manage user"})}"
                                    `}
                          >
                              ${{
                                  __html: render_icon_button({
                                      disabled: context.cannot_edit,
                                      custom_classes: "open-user-form manage-user-button",
                                      intent: "neutral",
                                      icon: "user-cog",
                                  }),
                              }}
                          </span>
                          ${to_bool(context.is_active)
                              ? html`
                                    <span
                                        class="${to_bool(context.is_bot)
                                            ? "deactivate-bot-tooltip"
                                            : "deactivate-user-tooltip"} ${to_bool(
                                            context.cannot_deactivate,
                                        )
                                            ? "tippy-zulip-tooltip"
                                            : ""}"
                                        ${to_bool(context.is_bot) &&
                                        to_bool(context.cannot_deactivate)
                                            ? html`data-tippy-content="${$t({
                                                  defaultMessage: "This bot cannot be deactivated.",
                                              })}"`
                                            : to_bool(context.cannot_deactivate)
                                              ? html`data-tippy-content="${$t({
                                                    defaultMessage:
                                                        "This user cannot be deactivated.",
                                                })}"`
                                              : ""}
                                    >
                                        ${{
                                            __html: render_icon_button({
                                                disabled: context.cannot_deactivate,
                                                custom_classes: "deactivate",
                                                intent: "danger",
                                                icon: "user-x",
                                            }),
                                        }}
                                    </span>
                                `
                              : html`
                                    <span
                                        class="${to_bool(context.is_bot)
                                            ? "reactivate-bot-tooltip"
                                            : "reactivate-user-tooltip"}"
                                    >
                                        ${{
                                            __html: render_icon_button({
                                                custom_classes: "reactivate",
                                                intent: "success",
                                                icon: "user-plus",
                                            }),
                                        }}
                                    </span>
                                `}
                      </span>
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
