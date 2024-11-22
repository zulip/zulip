import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$html_t, $t} from "../../../src/i18n.ts";

export default function render_left_sidebar_recent_view_popover(context) {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list">
            ${to_bool(context.is_home_view)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              id="mark_all_messages_as_read"
                              class="popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-mark-as-read"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Mark all messages as read"})}</span
                              >
                          </a>
                      </li>
                  `
                : html`
                      <li role="none" class="link-item popover-menu-list-item">
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
                                  ${$html_t({
                                      defaultMessage:
                                          "Make <b>recent conversations</b> my home view",
                                  })}
                              </span>
                          </a>
                      </li>
                  `}
        </ul>
    </div> `;
    return to_html(out);
}
