import {html, to_html} from "../../../shared/src/html.ts";
import {popover_hotkey_hints} from "../../../src/common.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";
import render_user_display_only_pill from "../../user_display_only_pill.ts";
import render_user_full_name from "../../user_full_name.ts";
import render_user_card_popover_custom_fields from "./user_card_popover_custom_fields.ts";

export default function render_user_card_popover(context) {
    const out = html`<div
        class="popover-menu user-card-popover-actions no-auto-hide-right-sidebar-overlay"
        id="user_card_popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="popover-menu-user-header">
            <div class="popover-menu-user-avatar-container">
                <img
                    class="popover-menu-user-avatar${to_bool(context.user_is_guest)
                        ? " guest-avatar"
                        : ""}"
                    src="${context.user_avatar}"
                />
                ${to_bool(context.is_active) && !to_bool(context.is_bot)
                    ? html`
                          <div
                              class="popover-menu-user-presence user_circle ${context.user_circle_class} hidden-for-spectators"
                              data-presence-indicator-user-id="${context.user_id}"
                          ></div>
                      `
                    : ""}
            </div>
            <div class="popover-menu-user-info">
                <div
                    class="popover-menu-user-full-name"
                    data-tippy-content="${context.user_full_name}"
                >
                    ${{__html: render_user_full_name({name: context.user_full_name})}}${to_bool(
                        context.is_bot,
                    )
                        ? html` <i class="zulip-icon zulip-icon-bot" aria-hidden="true"></i> `
                        : ""}
                </div>
                <div class="popover-menu-user-type">
                    ${to_bool(context.is_bot)
                        ? to_bool(context.is_system_bot)
                            ? html` <div>${$t({defaultMessage: "System bot"})}</div> `
                            : html`
                                  <div>
                                      ${$t({defaultMessage: "Bot"})}${context.user_type !== "Member"
                                          ? html`
                                                <span class="lowercase"
                                                    >(${context.user_type})</span
                                                >
                                            `
                                          : ""}
                                  </div>
                              `
                        : html` <div>${context.user_type}</div> `}
                </div>
            </div>
        </div>
        <ul role="menu" class="popover-menu-list" data-user-id="${context.user_id}">
            ${to_bool(context.status_content_available)
                ? html`
                      <li
                          role="none"
                          class="text-item popover-menu-list-item hidden-for-spectators"
                      >
                          <span class="personal-menu-status-wrapper">
                              ${to_bool(context.status_emoji_info)
                                  ? to_bool(context.status_emoji_info.emoji_alt_code)
                                      ? html`
                                            <span class="emoji_alt_code"
                                                >&nbsp;:${context.status_emoji_info
                                                    .emoji_name}:</span
                                            >
                                        `
                                      : to_bool(context.status_emoji_info.url)
                                        ? html`
                                              <img
                                                  src="${context.status_emoji_info.url}"
                                                  class="emoji status_emoji"
                                                  data-tippy-content=":${context.status_emoji_info
                                                      .emoji_name}:"
                                              />
                                          `
                                        : html`
                                              <span
                                                  class="emoji status_emoji emoji-${context
                                                      .status_emoji_info.emoji_code}"
                                                  data-tippy-content=":${context.status_emoji_info
                                                      .emoji_name}:"
                                              ></span>
                                          `
                                  : ""}
                              <span class="status_text personal-menu-status-text">
                                  ${to_bool(context.show_placeholder_for_status_text)
                                      ? html`
                                            <i class="personal-menu-no-status-text"
                                                >${$t({defaultMessage: "No status text"})}</i
                                            >
                                        `
                                      : html` ${context.status_text} `}
                              </span>
                          </span>
                          ${to_bool(context.is_me)
                              ? html`
                                    <a
                                        role="menuitem"
                                        tabindex="0"
                                        class="personal-menu-clear-status user-card-clear-status-button popover-menu-link"
                                        aria-label="${$t({defaultMessage: "Clear status"})}"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Clear your status",
                                        })}"
                                    >
                                        <i
                                            class="personal-menu-clear-status-icon popover-menu-icon zulip-icon zulip-icon-x-circle"
                                            aria-hidden="true"
                                        ></i>
                                    </a>
                                `
                              : ""}
                      </li>
                  `
                : ""}${to_bool(context.is_me)
                ? html`${to_bool(context.status_content_available)
                      ? html`
                            <li
                                role="none"
                                class="link-item popover-menu-list-item hidden-for-spectators"
                            >
                                <a
                                    role="menuitem"
                                    tabindex="0"
                                    class="update_status_text popover-menu-link"
                                >
                                    <i
                                        class="popover-menu-icon zulip-icon zulip-icon-smile-smaller"
                                        aria-hidden="true"
                                    ></i>
                                    <span class="popover-menu-label"
                                        >${$t({defaultMessage: "Edit status"})}</span
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
                                    tabindex="0"
                                    class="update_status_text popover-menu-link"
                                >
                                    <i
                                        class="popover-menu-icon zulip-icon zulip-icon-smile-smaller"
                                        aria-hidden="true"
                                    ></i>
                                    <span class="popover-menu-label"
                                        >${$t({defaultMessage: "Set status"})}</span
                                    >
                                </a>
                            </li>
                        `}${to_bool(context.invisible_mode)
                      ? html`
                            <li role="none" class="link-item popover-menu-list-item">
                                <a
                                    role="menuitem"
                                    tabindex="0"
                                    class="invisible_mode_turn_off popover-menu-link"
                                >
                                    <i
                                        class="popover-menu-icon zulip-icon zulip-icon-play-circle"
                                        aria-hidden="true"
                                    ></i>
                                    <span class="popover-menu-label"
                                        >${$t({defaultMessage: "Turn off invisible mode"})}</span
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
                                    tabindex="0"
                                    class="invisible_mode_turn_on popover-menu-link"
                                >
                                    <i
                                        class="popover-menu-icon zulip-icon zulip-icon-stop-circle"
                                        aria-hidden="true"
                                    ></i>
                                    <span class="popover-menu-label"
                                        >${$t({defaultMessage: "Go invisible"})}</span
                                    >
                                </a>
                            </li>
                        `}`
                : ""}${to_bool(context.is_me) || to_bool(context.status_content_available)
                ? html`
                      <li
                          role="separator"
                          class="popover-menu-separator hidden-for-spectators"
                      ></li>
                  `
                : ""}${to_bool(context.is_active)
                ? html`${!to_bool(context.is_bot)
                      ? html`
                            <li
                                role="none"
                                class="popover-menu-list-item text-item hidden-for-spectators"
                            >
                                <i
                                    class="popover-menu-icon zulip-icon zulip-icon-past-time"
                                    aria-hidden="true"
                                ></i>
                                <span class="popover-menu-label"
                                    >${context.user_last_seen_time_status}</span
                                >
                            </li>
                        `
                      : ""}${to_bool(context.user_time)
                      ? html`
                            <li
                                role="none"
                                class="popover-menu-list-item text-item hidden-for-spectators"
                            >
                                <i
                                    class="popover-menu-icon zulip-icon zulip-icon-clock"
                                    aria-hidden="true"
                                ></i>
                                <span class="popover-menu-label"
                                    >${$t(
                                        {defaultMessage: "{user_time} local time"},
                                        {user_time: context.user_time},
                                    )}</span
                                >
                            </li>
                        `
                      : ""}`
                : html`
                      <li
                          role="none"
                          class="popover-menu-list-item text-item italic hidden-for-spectators"
                      >
                          ${to_bool(context.is_bot)
                              ? html`
                                    <span class="popover-menu-label"
                                        >${$t({
                                            defaultMessage: "This bot has been deactivated.",
                                        })}</span
                                    >
                                `
                              : html`
                                    <span class="popover-menu-label"
                                        >${$t({
                                            defaultMessage: "This user has been deactivated.",
                                        })}</span
                                    >
                                `}
                      </li>
                  `}${to_bool(context.spectator_view)
                ? html`
                      <li role="none" class="popover-menu-list-item text-item">
                          <span class="popover-menu-label"
                              >${$t(
                                  {defaultMessage: "Joined {date_joined}"},
                                  {date_joined: context.date_joined},
                              )}</span
                          >
                      </li>
                  `
                : ""}
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            ${to_bool(context.is_bot)
                ? to_bool(context.bot_owner)
                    ? html`
                          <li
                              role="none"
                              class="popover-menu-list-item user-card-popover-bot-owner-field text-item hidden-for-spectators"
                          >
                              <span
                                  class="bot_owner"
                                  data-tippy-content="${context.bot_owner.full_name}"
                                  >${$t({defaultMessage: "Bot owner"})}:</span
                              >
                              ${{
                                  __html: render_user_display_only_pill({
                                      is_active: true,
                                      img_src: context.bot_owner.avatar_url,
                                      user_id: context.bot_owner.user_id,
                                      display_value: context.bot_owner.full_name,
                                  }),
                              }}
                          </li>
                      `
                    : ""
                : ""}${to_bool(context.is_active)
                ? to_bool(context.user_email)
                    ? html`
                          <li
                              role="none"
                              class="popover-menu-list-item text-item user-card-popover-email-field hidden-for-spectators"
                          >
                              <span class="user_popover_email">${context.user_email}</span>
                              <span
                                  role="menuitem"
                                  tabindex="0"
                                  id="popover-menu-copy-email"
                                  class="popover-menu-link copy-button hide_copy_icon"
                                  aria-label="${$t({defaultMessage: "Copy email"})}"
                                  data-tippy-content="${$t({defaultMessage: "Copy email"})}"
                                  data-clipboard-text="${context.user_email}"
                              >
                                  <i class="zulip-icon zulip-icon-copy hide" aria-hidden="true"></i>
                              </span>
                          </li>
                      `
                    : ""
                : ""}
            ${{
                __html: render_user_card_popover_custom_fields({
                    profile_fields: context.display_profile_fields,
                }),
            }}
            <li role="none" class="popover-menu-list-item link-item hidden-for-spectators">
                <a role="menuitem" class="popover-menu-link view_full_user_profile" tabindex="0">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-account"
                        aria-hidden="true"
                    ></i>
                    ${to_bool(context.is_me)
                        ? html`
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "View your profile"})}</span
                              >
                          `
                        : html`
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "View profile"})}</span
                              >
                          `}
                </a>
            </li>
            ${to_bool(context.can_send_private_message)
                ? html`
                      <li
                          role="none"
                          class="popover-menu-list-item link-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              class="popover-menu-link ${context.private_message_class}"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-send-dm"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Send direct message"})}</span
                              >
                              ${to_bool(context.is_sender_popover)
                                  ? html` ${popover_hotkey_hints("R")} `
                                  : ""}
                          </a>
                      </li>
                  `
                : ""}${!to_bool(context.is_me)
                ? html`
                      <li
                          role="none"
                          class="popover-menu-list-item link-item hidden-for-spectators"
                      >
                          ${to_bool(context.has_message_context)
                              ? html`
                                    <a
                                        role="menuitem"
                                        class="popover-menu-link mention_user"
                                        tabindex="0"
                                    >
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-at-sign"
                                            aria-hidden="true"
                                        ></i>
                                        ${to_bool(context.is_bot)
                                            ? html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Reply mentioning bot",
                                                      })}</span
                                                  >
                                              `
                                            : html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Reply mentioning user",
                                                      })}</span
                                                  >
                                              `}${to_bool(context.is_sender_popover)
                                            ? html` ${popover_hotkey_hints("@")} `
                                            : ""}
                                    </a>
                                `
                              : html`
                                    <a
                                        role="menuitem"
                                        class="popover-menu-link copy_mention_syntax"
                                        tabindex="0"
                                        data-clipboard-text="${context.user_mention_syntax}"
                                    >
                                        <i
                                            class="popover-menu-icon fa zulip-icon zulip-icon-at-sign"
                                            aria-hidden="true"
                                        ></i>
                                        <span class="popover-menu-label"
                                            >${$t({defaultMessage: "Copy mention syntax"})}</span
                                        >
                                        ${to_bool(context.is_sender_popover)
                                            ? html` ${popover_hotkey_hints("@")} `
                                            : ""}
                                    </a>
                                `}
                      </li>
                  `
                : ""}${to_bool(context.is_me)
                ? html`
                      <li
                          role="none"
                          class="popover-menu-list-item link-item hidden-for-spectators"
                      >
                          <a
                              role="menuitem"
                              class="popover-menu-link edit-your-profile"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-tool"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Edit your profile"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            <li role="none" class="popover-menu-list-item link-item">
                <a
                    role="menuitem"
                    href="${context.pm_with_url}"
                    class="narrow_to_private_messages popover-menu-link hidden-for-spectators"
                    tabindex="0"
                >
                    <i class="popover-menu-icon zulip-icon zulip-icon-user" aria-hidden="true"></i>
                    ${to_bool(context.is_me)
                        ? html`
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "View messages with yourself"})}</span
                              >
                          `
                        : html`
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "View direct messages"})}</span
                              >
                          `}
                </a>
            </li>
            <li role="none" class="popover-menu-list-item link-item">
                <a
                    role="menuitem"
                    href="${context.sent_by_url}"
                    class="narrow_to_messages_sent popover-menu-link hidden-for-spectators"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-message-square"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "View messages sent"})}</span
                    >
                </a>
            </li>
            ${to_bool(context.show_manage_section)
                ? html` <li
                          role="separator"
                          class="popover-menu-separator hidden-for-spectators"
                      ></li>
                      ${to_bool(context.can_mute)
                          ? html`
                                <li role="none" class="popover-menu-list-item link-item">
                                    <a
                                        role="menuitem"
                                        class="sidebar-popover-mute-user popover-menu-link hidden-for-spectators"
                                        tabindex="0"
                                    >
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-hide"
                                            aria-hidden="true"
                                        ></i>
                                        ${to_bool(context.is_bot)
                                            ? html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Mute this bot",
                                                      })}</span
                                                  >
                                              `
                                            : html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Mute this user",
                                                      })}</span
                                                  >
                                              `}
                                    </a>
                                </li>
                            `
                          : ""}${to_bool(context.can_unmute)
                          ? html`
                                <li role="none" class="popover-menu-list-item link-item">
                                    <a
                                        role="menuitem"
                                        class="sidebar-popover-unmute-user popover-menu-link hidden-for-spectators"
                                        tabindex="0"
                                    >
                                        <i
                                            class="popover-menu-icon fa fa-eye"
                                            aria-hidden="true"
                                        ></i>
                                        ${to_bool(context.is_bot)
                                            ? html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Unmute this bot",
                                                      })}</span
                                                  >
                                              `
                                            : html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Unmute this user",
                                                      })}</span
                                                  >
                                              `}
                                    </a>
                                </li>
                            `
                          : ""}${to_bool(context.can_manage_user)
                          ? html` <li
                                    role="separator"
                                    class="popover-menu-separator hidden-for-spectators"
                                ></li>
                                <li role="none" class="popover-menu-list-item link-item">
                                    <a
                                        role="menuitem"
                                        class="sidebar-popover-manage-user popover-menu-link hidden-for-spectators"
                                        tabindex="0"
                                    >
                                        <i
                                            class="popover-menu-icon zulip-icon zulip-icon-user-cog"
                                            aria-hidden="true"
                                        ></i>
                                        ${to_bool(context.is_bot)
                                            ? html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Manage this bot",
                                                      })}</span
                                                  >
                                              `
                                            : html`
                                                  <span class="popover-menu-label"
                                                      >${$t({
                                                          defaultMessage: "Manage this user",
                                                      })}</span
                                                  >
                                              `}
                                    </a>
                                </li>
                                ${!to_bool(context.is_active)
                                    ? html`
                                          <li role="none" class="popover-menu-list-item link-item">
                                              <a
                                                  role="menuitem"
                                                  class="sidebar-popover-reactivate-user popover-menu-link hidden-for-spectators"
                                                  tabindex="0"
                                              >
                                                  <i
                                                      class="popover-menu-icon zulip-icon zulip-icon-user-plus"
                                                      aria-hidden="true"
                                                  ></i>
                                                  ${to_bool(context.is_bot)
                                                      ? html`
                                                            <span class="popover-menu-label"
                                                                >${$t({
                                                                    defaultMessage:
                                                                        "Reactivate this bot",
                                                                })}</span
                                                            >
                                                        `
                                                      : html`
                                                            <span class="popover-menu-label"
                                                                >${$t({
                                                                    defaultMessage:
                                                                        "Reactivate this user",
                                                                })}</span
                                                            >
                                                        `}
                                              </a>
                                          </li>
                                      `
                                    : ""}`
                          : ""}`
                : ""}
        </ul>
    </div> `;
    return to_html(out);
}
