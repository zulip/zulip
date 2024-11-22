import {html, to_html} from "../../shared/src/html.ts";
import {popover_hotkey_hints} from "../../src/common.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_send_later_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="send_later_popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="popover-menu-list-item">
                <div
                    role="group"
                    class="enter_sends_choices"
                    aria-label="${$t({defaultMessage: "Enter to send choices"})}"
                >
                    <label role="menuitemradio" class="enter_sends_choice" tabindex="0">
                        <input
                            type="radio"
                            class="enter_sends_choice_radio"
                            name="enter_sends_choice"
                            value="true"
                            ${to_bool(context.enter_sends_true) ? " checked" : ""}
                        />
                        <div class="enter_sends_choice_text_container">
                            <span class="enter_sends_major enter_sends_choice_text">
                                ${$html_t(
                                    {defaultMessage: "Press <z-shortcut></z-shortcut> to send"},
                                    {["z-shortcut"]: () => popover_hotkey_hints("Enter")},
                                )}
                            </span>
                            <span class="enter_sends_minor enter_sends_choice_text">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Press <z-shortcut></z-shortcut> to add a new line",
                                    },
                                    {["z-shortcut"]: () => popover_hotkey_hints("Ctrl", "Enter")},
                                )}
                            </span>
                        </div>
                    </label>
                    <label role="menuitemradio" class="enter_sends_choice" tabindex="0">
                        <input
                            type="radio"
                            class="enter_sends_choice_radio"
                            name="enter_sends_choice"
                            value="false"
                            ${!to_bool(context.enter_sends_true) ? " checked" : ""}
                        />
                        <div class="enter_sends_choice_text_container">
                            <span class="enter_sends_major enter_sends_choice_text">
                                ${$html_t(
                                    {defaultMessage: "Press <z-shortcut></z-shortcut> to send"},
                                    {["z-shortcut"]: () => popover_hotkey_hints("Ctrl", "Enter")},
                                )}
                            </span>
                            <span class="enter_sends_minor enter_sends_choice_text">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "Press <z-shortcut></z-shortcut> to add a new line",
                                    },
                                    {["z-shortcut"]: () => popover_hotkey_hints("Enter")},
                                )}
                            </span>
                        </div>
                    </label>
                </div>
            </li>
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="link-item popover-menu-list-item">
                <a role="menuitem" class="open_send_later_modal popover-menu-link" tabindex="0">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-calendar"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Schedule message"})}</span
                    >
                </a>
            </li>
            ${to_bool(context.formatted_send_later_time)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="send_later_selected_send_later_time popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-calendar-clock"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t(
                                      {defaultMessage: "Schedule for {formatted_send_later_time}"},
                                      {
                                          formatted_send_later_time:
                                              context.formatted_send_later_time,
                                      },
                                  )}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    href="#scheduled"
                    role="menuitem"
                    class="navigate-link-on-enter popover-menu-link"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-calendar-days"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "View scheduled messages"})}</span
                    >
                </a>
            </li>
            <li role="separator" class="popover-menu-separator drafts-item-in-popover"></li>
            <li role="none" class="link-item popover-menu-list-item drafts-item-in-popover">
                <a
                    href="#drafts"
                    role="menuitem"
                    class="view_contextual_drafts popover-menu-link"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-drafts"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "View drafts"})}</span>
                    <span class="compose-drafts-count-container"
                        ><span class="unread_count quiet-count compose-drafts-count"></span
                    ></span>
                </a>
            </li>
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="link-item popover-menu-list-item saved-snippets-item-in-popover">
                <a
                    id="saved_snippets_widget"
                    role="menuitem"
                    class="view-saved-snippets popover-menu-link"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-message-square"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Saved snippets"})}</span
                    >
                </a>
            </li>
            ${to_bool(context.show_compose_new_message)
                ? html`
                      <li role="separator" class="popover-menu-separator"></li>
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="compose_new_message popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-file-check"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({
                                      defaultMessage: "Save draft and start a new message",
                                  })}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
