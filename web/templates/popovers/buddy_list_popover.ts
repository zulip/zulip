import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_buddy_list_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="buddy-list-actions-menu-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="link-item">
                <label class="display-style-selector-header popover-menu-link" role="menuitem">
                    <span class="popover-menu-label">
                        ${$t({defaultMessage: "User list style"})}
                    </span>
                </label>
            </li>
            ${to_array(context.display_style_options).map(
                (style) => html`
                    <li role="none" class="display-style-selector link-item" value="${style.code}">
                        <label class="popover-menu-link" role="menuitem" tabindex="0">
                            <input
                                type="radio"
                                class="user_list_style_choice"
                                name="user_list_style"
                                value="${style.code}"
                            />
                            <span class="popover-menu-label">${style.description}</span>
                        </label>
                    </li>
                `,
            )}${to_bool(context.can_invite_users)
                ? html`
                      <li role="none" class="invite-user-link-item link-item">
                          <a
                              class="invite-user-link popover-menu-link"
                              role="menuitem"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-user-plus"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label">
                                  ${$t({defaultMessage: "Invite users to organization"})}
                              </span>
                          </a>
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
