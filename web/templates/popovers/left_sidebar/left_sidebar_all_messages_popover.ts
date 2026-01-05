import {to_bool} from "../../../src/hbs_compat.ts";
import {html, to_html} from "../../../src/html.ts";
import {$html_t, $t} from "../../../src/i18n.ts";

export default function render_left_sidebar_all_messages_popover(context) {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list">
            ${to_bool(context.is_home_view)
                ? html`${to_bool(context.unread_messages_present)
                          ? html`
                                <li role="none" class="link-item popover-menu-list-item">
                                    <a
                                        role="menuitem"
                                        class="popover-menu-link mark_all_messages_as_read"
                                        tabindex="0"
                                    >
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-mark-as-read"
                                            aria-hidden="true"
                                        ></i>
                                        <span class="popover-menu-label"
                                            >${$t({defaultMessage: "Mark messages as read"})}</span
                                        >
                                    </a>
                                </li>
                            `
                          : ""}
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="popover-menu-link toggle_display_unread_message_count"
                              tabindex="0"
                          >
                              ${to_bool(context.show_unread_count)
                                  ? html`
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-hide"
                                            aria-hidden="true"
                                        ></i>
                                        <span class="popover-menu-label"
                                            >${$t({defaultMessage: "Hide unread counter"})}</span
                                        >
                                    `
                                  : html`
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-eye"
                                            aria-hidden="true"
                                        ></i>
                                        <span class="popover-menu-label"
                                            >${$t({defaultMessage: "Show unread counter"})}</span
                                        >
                                    `}
                          </a>
                      </li> `
                : html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item no-auto-hide-left-sidebar-overlay"
                      >
                          <a
                              role="menuitem"
                              class="set-home-view popover-menu-link"
                              data-view-code="${context.view_code}"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-house"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label">
                                  ${$html_t(
                                      {
                                          defaultMessage:
                                              "Make <z-highlight>combined feed</z-highlight> my home view",
                                      },
                                      {
                                          ["z-highlight"]: (content) =>
                                              html`<b class="highlighted-element">${content}</b>`,
                                      },
                                  )}
                              </span>
                          </a>
                      </li>
                  `}
        </ul>
    </div> `;
    return to_html(out);
}
