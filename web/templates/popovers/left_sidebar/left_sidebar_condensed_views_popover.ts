import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_left_sidebar_condensed_views_popover(context) {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list condensed-views-popover-menu">
            <li
                role="none"
                class="link-item popover-menu-list-item condensed-views-popover-menu-reactions"
            >
                <a
                    href="#narrow/has/reaction/sender/me"
                    role="menuitem"
                    class="popover-menu-link tippy-left-sidebar-tooltip"
                    data-tooltip-template-id="my-reactions-tooltip-template"
                    tabindex="0"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-smile" aria-hidden="true"></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Reactions"})}</span>
                </a>
            </li>
            <li
                role="none"
                class="link-item popover-menu-list-item condensed-views-popover-menu-drafts"
            >
                <a
                    href="#drafts"
                    role="menuitem"
                    class="popover-menu-link tippy-left-sidebar-tooltip"
                    data-tooltip-template-id="drafts-tooltip-template"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-drafts"
                        aria-hidden="true"
                    ></i>
                    <span class="label-and-unread-wrapper">
                        <span class="popover-menu-label">${$t({defaultMessage: "Drafts"})}</span>
                        <span class="unread_count quiet-count"></span>
                    </span>
                </a>
            </li>
            ${to_bool(context.has_scheduled_messages)
                ? html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item condensed-views-popover-menu-scheduled-messages"
                      >
                          <a
                              href="#scheduled"
                              role="menuitem"
                              class="popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-calendar-days"
                                  aria-hidden="true"
                              ></i>
                              <span class="label-and-unread-wrapper">
                                  <span class="popover-menu-label"
                                      >${$t({defaultMessage: "Scheduled messages"})}</span
                                  >
                                  <span class="unread_count quiet-count"></span>
                              </span>
                          </a>
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
