import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
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
                            class="popover-menu-icon zulip-icon zulip-icon-triple-users"
                            aria-hidden="true"
                        ></i>
                        <span class="popover-group-menu-name">${context.group_name}</span>
                    </div>
                    <div class="popover-group-menu-description">${context.group_description}</div>
                </div>
            </li>
            ${to_bool(context.members.length) || to_bool(context.subgroups.length)
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
                ${to_bool(context.members.length) || to_bool(context.subgroups.length)
                    ? html`
                          <ul
                              class="popover-menu-list popover-group-menu-member-list"
                              data-simplebar
                              data-simplebar-tab-index="-1"
                              data-simplebar-auto-hide="false"
                          >
                              ${to_array(context.subgroups).map(
                                  (subgroup) => html`
                                      <li class="popover-group-menu-member">
                                          <i
                                              class="popover-menu-icon zulip-icon zulip-icon-triple-users"
                                              aria-hidden="true"
                                          ></i>
                                          <span class="popover-group-menu-member-name"
                                              >${subgroup.name}</span
                                          >
                                      </li>
                                  `,
                              )}${to_array(context.members).map(
                                  (user) => html`
                                      <li class="popover-group-menu-member">
                                          ${to_bool(user.is_bot)
                                              ? html`
                                                    <i
                                                        class="zulip-icon zulip-icon-bot"
                                                        aria-hidden="true"
                                                    ></i>
                                                `
                                              : html`
                                                    <span
                                                        class="user_circle ${user.user_circle_class} popover_user_presence hidden-for-spectators"
                                                        data-tippy-content="${user.user_last_seen_time_status}"
                                                    ></span>
                                                `}
                                          <span class="popover-group-menu-member-name"
                                              >${user.full_name}</span
                                          >
                                      </li>
                                  `,
                              )}
                          </ul>
                      `
                    : html`
                          <span class="popover-group-menu-placeholder"
                              ><i>${$t({defaultMessage: "This group has no members."})}</i></span
                          >
                      `}
            </li>
            ${!(
                to_bool(context.is_guest) ||
                to_bool(context.is_system_group) ||
                to_bool(context.deactivated)
            )
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
                                  class="popover-menu-icon zulip-icon zulip-icon-user-cog"
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
