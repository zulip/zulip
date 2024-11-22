import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_left_sidebar_topic_actions_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="topic-actions-menu-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="popover-topic-header text-item popover-menu-list-item">
                <span class="popover-topic-name">${context.topic_name}</span>
            </li>
            ${/* Group 1 */ ""}${!to_bool(context.is_spectator)
                ? html`
                      <li role="separator" class="popover-menu-separator"></li>
                      <li role="none" class="popover-menu-list-item">
                          <div
                              role="group"
                              class="tab-picker popover-menu-tab-group"
                              aria-label="${$t({defaultMessage: "Topic visibility"})}"
                          >
                              <input
                                  type="radio"
                                  id="sidebar-topic-muted-policy"
                                  class="tab-option"
                                  name="sidebar-topic-visibility-select"
                                  data-visibility-policy="${context.all_visibility_policies.MUTED}"
                                  ${context.visibility_policy ===
                                  context.all_visibility_policies.MUTED
                                      ? "checked"
                                      : ""}
                              />
                              <label
                                  role="menuitemradio"
                                  class="tab-option-content tippy-zulip-delayed-tooltip"
                                  for="sidebar-topic-muted-policy"
                                  aria-label="${$t({defaultMessage: "Mute"})}"
                                  data-tippy-content="${$t({defaultMessage: "Mute"})}"
                                  tabindex="0"
                              >
                                  <i class="zulip-icon zulip-icon-mute-new" aria-hidden="true"></i>
                              </label>
                              <input
                                  type="radio"
                                  id="sidebar-topic-inherit-policy"
                                  class="tab-option"
                                  name="sidebar-topic-visibility-select"
                                  data-visibility-policy="${context.all_visibility_policies
                                      .INHERIT}"
                                  ${context.visibility_policy ===
                                  context.all_visibility_policies.INHERIT
                                      ? "checked"
                                      : ""}
                              />
                              <label
                                  role="menuitemradio"
                                  class="tab-option-content tippy-zulip-delayed-tooltip"
                                  for="sidebar-topic-inherit-policy"
                                  aria-label="${$t({defaultMessage: "Default"})}"
                                  data-tippy-content="${$t({defaultMessage: "Default"})}"
                                  tabindex="0"
                              >
                                  <i class="zulip-icon zulip-icon-inherit" aria-hidden="true"></i>
                              </label>
                              ${to_bool(context.stream_muted) || to_bool(context.topic_unmuted)
                                  ? html`
                                        <input
                                            type="radio"
                                            id="sidebar-topic-unmuted-policy"
                                            class="tab-option"
                                            name="sidebar-topic-visibility-select"
                                            data-visibility-policy="${context
                                                .all_visibility_policies.UNMUTED}"
                                            ${context.visibility_policy ===
                                            context.all_visibility_policies.UNMUTED
                                                ? "checked"
                                                : ""}
                                        />
                                        <label
                                            role="menuitemradio"
                                            class="tab-option-content tippy-zulip-delayed-tooltip"
                                            for="sidebar-topic-unmuted-policy"
                                            aria-label="${$t({defaultMessage: "Unmute"})}"
                                            data-tippy-content="${$t({defaultMessage: "Unmute"})}"
                                            tabindex="0"
                                        >
                                            <i
                                                class="zulip-icon zulip-icon-unmute-new"
                                                aria-hidden="true"
                                            ></i>
                                        </label>
                                    `
                                  : ""}
                              <input
                                  type="radio"
                                  id="sidebar-topic-followed-policy"
                                  class="tab-option"
                                  name="sidebar-topic-visibility-select"
                                  data-visibility-policy="${context.all_visibility_policies
                                      .FOLLOWED}"
                                  ${context.visibility_policy ===
                                  context.all_visibility_policies.FOLLOWED
                                      ? "checked"
                                      : ""}
                              />
                              <label
                                  role="menuitemradio"
                                  class="tab-option-content tippy-zulip-delayed-tooltip"
                                  for="sidebar-topic-followed-policy"
                                  aria-label="${$t({defaultMessage: "Follow"})}"
                                  data-tippy-content="${$t({defaultMessage: "Follow"})}"
                                  tabindex="0"
                              >
                                  <i class="zulip-icon zulip-icon-follow" aria-hidden="true"></i>
                              </label>
                              <span class="slider"></span>
                          </div>
                      </li>
                  `
                : ""}${/* Group 2 */ ""}
            <li role="separator" class="popover-menu-separator"></li>
            ${to_bool(context.has_starred_messages)
                ? html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              class="sidebar-popover-unstar-all-in-topic popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-star"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Unstar all messages in topic"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.has_unread_messages)
                ? html`
                      <li
                          role="none"
                          class="link-item popover-menu-list-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              class="sidebar-popover-mark-topic-read popover-menu-link"
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
                      <li
                          role="none"
                          class="link-item popover-menu-list-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              class="sidebar-popover-mark-topic-unread popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-mark-as-unread"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Mark all messages as unread"})}</span
                              >
                          </a>
                      </li>
                  `}
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="sidebar-popover-copy-link-to-topic popover-menu-link"
                    data-clipboard-text="${context.url}"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-link-alt"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Copy link to topic"})}</span
                    >
                </a>
            </li>
            ${/* Group 3 */ ""}${to_bool(context.can_move_topic) ||
            to_bool(context.can_rename_topic) ||
            to_bool(context.is_realm_admin)
                ? html` <li role="separator" class="popover-menu-separator"></li> `
                : ""}${to_bool(context.can_move_topic)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="sidebar-popover-move-topic-messages popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-move-alt"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Move topic"})}</span
                              >
                          </a>
                      </li>
                  `
                : to_bool(context.can_rename_topic)
                  ? html`
                        <li role="none" class="link-item popover-menu-list-item">
                            <a
                                role="menuitem"
                                class="sidebar-popover-rename-topic-messages popover-menu-link"
                                tabindex="0"
                            >
                                <i
                                    class="popover-menu-icon zulip-icon zulip-icon-rename"
                                    aria-hidden="true"
                                ></i>
                                <span class="popover-menu-label"
                                    >${$t({defaultMessage: "Rename topic"})}</span
                                >
                            </a>
                        </li>
                    `
                  : ""}${to_bool(context.can_rename_topic)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="sidebar-popover-toggle-resolved popover-menu-link"
                              tabindex="0"
                          >
                              ${to_bool(context.topic_is_resolved)
                                  ? html`
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-check-x"
                                            aria-hidden="true"
                                        ></i>
                                        <span class="popover-menu-label"
                                            >${$t({defaultMessage: "Mark as unresolved"})}</span
                                        >
                                    `
                                  : html`
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-check"
                                            aria-hidden="true"
                                        ></i>
                                        <span class="popover-menu-label"
                                            >${$t({defaultMessage: "Mark as resolved"})}</span
                                        >
                                    `}
                          </a>
                      </li>
                  `
                : ""}${to_bool(context.is_realm_admin)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="sidebar-popover-delete-topic-messages popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-trash"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Delete topic"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
