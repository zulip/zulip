import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";

export default function render_user_group_list_item(context) {
    const out = html`<li
        class="group-list-item"
        role="presentation"
        data-group-id="${context.group_id}"
    >
        <a class="user-profile-group-row hidden-remove-button-row" href="${context.group_edit_url}">
            <span class="user-group-name"> ${context.name} </span>
            ${to_bool(context.can_remove_members)
                ? html`
                      <div class="remove-button-wrapper">
                          ${to_bool(context.is_direct_member)
                              ? html` ${{
                                    __html: render_icon_button({
                                        ["data-tippy-content"]: $t({defaultMessage: "Remove"}),
                                        ["aria-label"]: $t({defaultMessage: "Remove"}),
                                        intent: "danger",
                                        custom_classes:
                                            "hidden-remove-button remove-member-button tippy-zulip-delayed-tooltip",
                                        icon: "close",
                                    }),
                                }}`
                              : html`
                                    <span
                                        class="tippy-zulip-tooltip"
                                        data-tippy-content="${to_bool(context.is_me)
                                            ? html`${$t(
                                                  {
                                                      defaultMessage:
                                                          "You are a member of {name} because you are a member of a subgroup ({subgroups_name}).",
                                                  },
                                                  {
                                                      name: context.name,
                                                      subgroups_name: context.subgroups_name,
                                                  },
                                              )} `
                                            : $t(
                                                  {
                                                      defaultMessage:
                                                          "This user is a member of {name} because they are a member of a subgroup ({subgroups_name}).",
                                                  },
                                                  {
                                                      name: context.name,
                                                      subgroups_name: context.subgroups_name,
                                                  },
                                              )}"
                                    >
                                        ${{
                                            __html: render_icon_button({
                                                disabled: "disabled",
                                                ["data-tippy-content"]: $t({
                                                    defaultMessage: "Remove",
                                                }),
                                                ["aria-label"]: $t({defaultMessage: "Remove"}),
                                                intent: "danger",
                                                custom_classes:
                                                    "hidden-remove-button remove-member-button tippy-zulip-delayed-tooltip",
                                                icon: "close",
                                            }),
                                        }}
                                    </span>
                                `}
                      </div>
                  `
                : ""}
        </a>
    </li> `;
    return to_html(out);
}
