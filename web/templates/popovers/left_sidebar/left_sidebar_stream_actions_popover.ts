import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";
import render_stream_privacy from "../../stream_privacy.ts";

export default function render_left_sidebar_stream_actions_popover(context) {
    const out = html`<div
        class="popover-menu"
        id="stream-actions-menu-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul
            role="menu"
            class="popover-menu-list"
            data-stream-id="${context.stream.stream_id}"
            data-name="${context.stream.name}"
        >
            <li role="none" class="popover-stream-header text-item popover-menu-list-item">
                <span
                    class="stream-privacy-original-color-${context.stream
                        .stream_id} stream-privacy filter-icon"
                    style="color: ${context.stream.color}"
                >
                    ${{
                        __html: render_stream_privacy({
                            is_web_public: context.stream.is_web_public,
                            invite_only: context.stream.invite_only,
                        }),
                    }}
                </span>
                <span class="popover-stream-name">${context.stream.name}</span>
            </li>
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a role="menuitem" class="mark_stream_as_read popover-menu-link" tabindex="0">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-mark-as-read"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Mark all messages as read"})}</span
                    >
                </a>
            </li>
            ${to_bool(context.show_go_to_channel_feed)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              class="stream-popover-go-to-channel-feed popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-all-messages"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Go to channel feed"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    class="copy_stream_link popover-menu-link"
                    data-clipboard-text="${context.stream.url}"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-link-alt"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Copy link to channel"})}</span
                    >
                </a>
            </li>
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a role="menuitem" class="open_stream_settings popover-menu-link" tabindex="0">
                    <i class="popover-menu-icon zulip-icon zulip-icon-gear" aria-hidden="true"></i>
                    <span class="popover-menu-label"
                        >${$t({defaultMessage: "Channel settings"})}</span
                    >
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a role="menuitem" class="pin_to_top popover-menu-link" tabindex="0">
                    ${to_bool(context.stream.pin_to_top)
                        ? html`
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-unpin"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Unpin channel from top"})}</span
                              >
                          `
                        : html`
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-pin"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Pin channel to top"})}</span
                              >
                          `}
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a role="menuitem" class="toggle_stream_muted popover-menu-link" tabindex="0">
                    ${to_bool(context.stream.is_muted)
                        ? html`
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-unmute-new"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Unmute channel"})}</span
                              >
                          `
                        : html`
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-mute-new"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Mute channel"})}</span
                              >
                          `}
                </a>
            </li>
            <li role="none" class="link-item popover-menu-list-item hidden-for-spectators">
                <a role="menuitem" class="popover_sub_unsub_button popover-menu-link" tabindex="0">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-circle-x"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Unsubscribe"})}</span>
                </a>
            </li>
            <li role="separator" class="popover-menu-separator hidden-for-spectators"></li>
            <li
                role="none"
                class="link-item popover-menu-list-item hidden-for-spectators no-auto-hide-left-sidebar-overlay"
            >
                <span class="colorpicker-container">
                    <input
                        stream_id="${context.stream.stream_id}"
                        class="colorpicker"
                        type="text"
                        value="${context.stream.color}"
                    />
                </span>
                <a role="menuitem" class="choose_stream_color popover-menu-link" tabindex="0">
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-pipette"
                        aria-hidden="true"
                    ></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Change color"})}</span>
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}
