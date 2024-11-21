import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_stream_member_list_entry(context) {
    const out = html`<tr data-subscriber-id="${context.user_id}" class="hidden-remove-button-row">
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
                  <td class="unsubscribe remove-button-wrapper remove-button-column">
                      ${to_bool(context.for_user_group_members)
                          ? html` ${{
                                __html: render_icon_button({
                                    ["data-tippy-content"]: $t({defaultMessage: "Remove"}),
                                    ["aria-label"]: $t({defaultMessage: "Remove"}),
                                    intent: "danger",
                                    custom_classes:
                                        "hidden-remove-button remove-subscriber-button tippy-zulip-delayed-tooltip",
                                    icon: "close",
                                }),
                            }}`
                          : html` ${{
                                __html: render_icon_button({
                                    ["data-tippy-content"]: $t({defaultMessage: "Unsubscribe"}),
                                    ["aria-label"]: $t({defaultMessage: "Unsubscribe"}),
                                    intent: "danger",
                                    custom_classes:
                                        "hidden-remove-button remove-subscriber-button tippy-zulip-delayed-tooltip",
                                    icon: "close",
                                }),
                            }}`}
                  </td>
              `
            : ""}
    </tr> `;
    return to_html(out);
}
