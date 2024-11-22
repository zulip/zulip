import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_left_sidebar_starred_messages_popover(context) {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list">
            ${to_bool(context.show_unstar_all_button)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              id="unstar_all_messages"
                              class="popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-star"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Unstar all messages"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    id="toggle_display_starred_msg_count"
                    class="popover-menu-link"
                    tabindex="0"
                >
                    ${to_bool(context.starred_message_counts)
                        ? html`
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-hide"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Hide starred message count"})}</span
                              >
                          `
                        : html`
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-eye"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Show starred message count"})}</span
                              >
                          `}
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
