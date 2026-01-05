import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_user_group_info_popover(context) {
    const out = html`<div
        class="popover-menu user-group-info-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item popover-menu-list-item">
                <div class="popover-group-menu-info">
                    <div class="popover-group-menu-name-container">
                        <i
                            class="popover-menu-icon zulip-icon zulip-icon-user-group"
                            aria-hidden="true"
                        ></i>
                        <span class="popover-group-menu-name">${context.group_name}</span>
                    </div>
                    ${to_bool(context.group_description)
                        ? html`
                              <div class="popover-group-menu-description">
                                  ${context.group_description}
                              </div>
                          `
                        : ""}
                </div>
            </li>
            ${to_bool(context.displayed_members.length) ||
            to_bool(context.displayed_subgroups.length)
                ? to_bool(context.user_can_access_all_other_users)
                    ? html`
                          <li role="none" class="popover-menu-list-item text-item italic">
                              ${$html_t(
                                  {
                                      defaultMessage:
                                          "{members_count, plural, =1 {1 member} other {# members}}",
                                  },
                                  {members_count: context.members_count},
                              )}
                          </li>
                      `
                    : ""
                : ""}${to_bool(context.deactivated)
                ? html`
                      <li
                          role="none"
                          class="popover-menu-list-item text-item italic hidden-for-spectators"
                      >
                          <span class="popover-menu-label"
                              >${$t({defaultMessage: "This group has been deactivated."})}</span
                          >
                      </li>
                  `
                : ""}
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="popover-menu-list-item">
                ${to_bool(context.displayed_members.length) ||
                to_bool(context.displayed_subgroups.length)
                    ? html`
                          <ul
                              class="popover-menu-list popover-group-menu-member-list"
                              data-simplebar
                              data-simplebar-tab-index="-1"
                              data-simplebar-auto-hide="false"
                          >
                              ${to_array(context.displayed_subgroups).map(
                                  (subgroup) => html`
                                      <li class="popover-group-menu-member">
                                          <i
                                              class="popover-group-member-icon popover-menu-icon zulip-icon zulip-icon-user-group"
                                              aria-hidden="true"
                                          ></i>
                                          <span class="popover-group-menu-member-name"
                                              >${subgroup.name}</span
                                          >
                                      </li>
                                  `,
                              )}${to_array(context.displayed_members).map(
                                  (member) => html`
                                      <li class="popover-group-menu-member">
                                          ${to_bool(member.is_bot)
                                              ? html`
                                                    <i
                                                        class="popover-group-member-icon zulip-icon zulip-icon-bot"
                                                        aria-hidden="true"
                                                    ></i>
                                                `
                                              : html`
                                                    <span
                                                        class="popover-group-member-icon user-circle zulip-icon zulip-icon-${member.user_circle_class} ${member.user_circle_class} popover-group-menu-user-presence hidden-for-spectators"
                                                        data-tippy-content="${member.user_last_seen_time_status}"
                                                    ></span>
                                                `}
                                          <span class="popover-group-menu-member-name"
                                              >${member.full_name}</span
                                          >
                                      </li>
                                  `,
                              )}${!to_bool(context.display_all_subgroups_and_members)
                                  ? html`
                                        <li class="popover-group-menu-member">
                                            <span class="popover-group-menu-member-name">
                                                ${to_bool(context.is_system_group)
                                                    ? to_bool(context.has_bots)
                                                        ? $html_t(
                                                              {
                                                                  defaultMessage:
                                                                      "View all <z-link-users>users</z-link-users> and <z-link-bots>bots</z-link-bots>",
                                                              },
                                                              {
                                                                  ["z-link-users"]: (content) =>
                                                                      html`<a
                                                                          href="#organization/users"
                                                                          >${content}</a
                                                                      >`,
                                                                  ["z-link-bots"]: (content) =>
                                                                      html`<a
                                                                          href="#organization/bots"
                                                                          >${content}</a
                                                                      >`,
                                                              },
                                                          )
                                                        : html`
                                                              <a
                                                                  href="#organization/users"
                                                                  role="menuitem"
                                                              >
                                                                  ${$t({
                                                                      defaultMessage:
                                                                          "View all users",
                                                                  })}
                                                              </a>
                                                          `
                                                    : html`
                                                          <a
                                                              href="${context.group_members_url}"
                                                              role="menuitem"
                                                          >
                                                              ${$t({
                                                                  defaultMessage:
                                                                      "View all members",
                                                              })}
                                                          </a>
                                                      `}
                                            </span>
                                        </li>
                                    `
                                  : ""}
                          </ul>
                      `
                    : html`
                          <span class="popover-group-menu-placeholder"
                              ><i>${$t({defaultMessage: "This group has no members."})}</i></span
                          >
                      `}
            </li>
            ${!(to_bool(context.is_guest) || to_bool(context.is_system_group))
                ? html`
                      <li
                          role="separator"
                          class="popover-menu-separator hidden-for-spectators"
                      ></li>
                      <li
                          role="none"
                          class="link-item popover-menu-list-item hidden-for-spectators"
                      >
                          <a
                              href="${context.group_edit_url}"
                              role="menuitem"
                              class="navigate-link-on-enter popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-user-group-cog"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Group settings"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
