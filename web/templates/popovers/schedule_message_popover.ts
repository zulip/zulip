import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_schedule_message_popover(context) {
    const out = html`<div
        class="popover-menu ${to_bool(context.is_reminder) ? "message-reminder-popover" : ""}"
        id="send-later-options"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="text-item popover-menu-list-item">
                <span class="popover-header-name">
                    ${to_bool(context.is_reminder)
                        ? html` ${$t({defaultMessage: "Schedule reminder"})} `
                        : html` ${$t({defaultMessage: "Schedule message"})} `}
                </span>
            </li>
            ${to_bool(context.is_reminder)
                ? html`
                      <li role="separator" class="popover-menu-separator"></li>
                      <li
                          role="none"
                          class="text-item popover-menu-list-item schedule-reminder-note-item"
                      >
                          <textarea
                              class="schedule-reminder-note"
                              placeholder="${$t({defaultMessage: "Note"})}"
                              tabindex="0"
                              maxlength="${context.max_reminder_note_length}"
                          ></textarea>
                      </li>
                  `
                : ""}${to_bool(context.possible_send_later_today)
                ? html` <li role="separator" class="popover-menu-separator"></li>
                      ${Object.entries(context.possible_send_later_today).map(
                          ([option_key, option]) => html`
                              <li role="none" class="link-item popover-menu-list-item">
                                  <a
                                      role="menuitem"
                                      id="${option_key}"
                                      class="send_later_today send_later_option popover-menu-link"
                                      data-send-stamp="${option.stamp}"
                                      tabindex="0"
                                  >
                                      <span class="popover-menu-label">${option.text}</span>
                                  </a>
                              </li>
                          `,
                      )}`
                : ""}
            <li role="separator" class="popover-menu-separator"></li>
            ${Object.entries(context.send_later_tomorrow).map(
                ([option_key, option]) => html`
                    <li role="none" class="link-item popover-menu-list-item">
                        <a
                            role="menuitem"
                            id="${option_key}"
                            class="send_later_tomorrow send_later_option popover-menu-link"
                            data-send-stamp="${option.stamp}"
                            tabindex="0"
                        >
                            <span class="popover-menu-label">${option.text}</span>
                        </a>
                    </li>
                `,
            )}${to_bool(context.possible_send_later_monday)
                ? html` <li role="separator" class="popover-menu-separator"></li>
                      ${Object.entries(context.possible_send_later_monday).map(
                          ([option_key, option]) => html`
                              <li role="none" class="link-item popover-menu-list-item">
                                  <a
                                      role="menuitem"
                                      id="${option_key}"
                                      class="send_later_monday send_later_option popover-menu-link"
                                      data-send-stamp="${option.stamp}"
                                      tabindex="0"
                                  >
                                      <span class="popover-menu-label">${option.text}</span>
                                  </a>
                              </li>
                          `,
                      )}`
                : ""}
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="send_later_custom send_later_option popover-menu-link"
                    tabindex="0"
                >
                    <span class="popover-menu-label">${$t({defaultMessage: "Custom time"})}</span>
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
