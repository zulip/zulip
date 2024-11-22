import {html, to_html} from "../../shared/src/html.ts";
import {popover_hotkey_hints} from "../../src/common.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_message_actions_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="message-actions-menu-dropdown"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            ${/* Group 1 */ ""}${to_bool(context.should_display_quote_and_reply)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="respond_button popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-quote-and-reply"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Quote and reply"})}</span
                              >
                              ${popover_hotkey_hints(">")}
                          </a>
                      </li>
                  `
                : ""}${/* Group 2 */ ""}${to_bool(context.editability_menu_item) ||
            to_bool(context.move_message_menu_item) ||
            to_bool(context.should_display_delete_option)
                ? html` <li role="separator" class="popover-menu-separator"></li> `
                : ""}${to_bool(context.editability_menu_item)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="popover_edit_message popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-edit"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${context.editability_menu_item}</span
                              >
                              ${popover_hotkey_hints("E")}
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.move_message_menu_item)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="popover_move_message popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-move-alt"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${context.move_message_menu_item}</span
                              >
                              ${popover_hotkey_hints("M")}
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.should_display_delete_option)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="delete_message popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-trash"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Delete message"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${/* Group 3 */ ""}${to_bool(context.should_display_add_reaction_option)
                ? html`
                      <li role="separator" class="popover-menu-separator"></li>
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="reaction_button popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-smile"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Add emoji reaction"})}</span
                              >
                              ${popover_hotkey_hints(":")}
                          </a>
                      </li>
                  `
                : ""}${/* Group 4 */ ""}${to_bool(context.should_display_mark_as_unread) ||
            to_bool(context.should_display_hide_option) ||
            to_bool(context.should_display_collapse) ||
            to_bool(context.should_display_uncollapse)
                ? html` <li role="separator" class="popover-menu-separator"></li> `
                : ""}${to_bool(context.should_display_mark_as_unread)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="mark_as_unread popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-mark-as-unread"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Mark as unread from here"})}</span
                              >
                              ${popover_hotkey_hints("Shift", "U")}
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.should_display_hide_option)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="rehide_muted_user_message popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-hide"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Hide muted message again"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.should_display_collapse)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="popover_toggle_collapse popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-collapse"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Collapse message"})}</span
                              >
                              ${popover_hotkey_hints("-")}
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.should_display_uncollapse)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="popover_toggle_collapse popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-expand"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Expand message"})}</span
                              >
                              ${popover_hotkey_hints("-")}
                          </a>
                      </li>
                  `
                : ""}${/* Group 5 */ ""}
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            ${to_bool(context.view_source_menu_item)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="popover_view_source popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-source"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${context.view_source_menu_item}</span
                              >
                              ${popover_hotkey_hints("E")}
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.should_display_read_receipts_option)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              data-message-id="${context.message_id}"
                              class="view_read_receipts popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-readreceipts"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "View read receipts"})}</span
                              >
                              ${popover_hotkey_hints("Shift", "V")}
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="copy_link navigate-link-on-enter popover-menu-link"
                    data-message-id="${context.message_id}"
                    data-clipboard-text="${context.conversation_time_url}"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-link-alt"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Copy link to message"})}</span
                    >
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
