import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_stream_sidebar_row(context) {
    const out = /* Stream sidebar rows */ html`
        <li
            class="narrow-filter${to_bool(context.is_muted) ? " out_of_home_view" : ""}"
            data-stream-id="${context.id}"
        >
            <div class="bottom_left_row">
                <a
                    href="${context.url}"
                    class="subscription_block selectable_sidebar_block"
                    draggable="false"
                >
                    <span
                        class="stream-privacy-original-color-${context.id} stream-privacy filter-icon"
                        style="color: ${context.color}"
                    >
                        ${{__html: render_stream_privacy(context)}}
                    </span>

                    <span class="stream-name">${context.name}</span>

                    <div class="left-sidebar-controls">
                        ${to_bool(context.can_post_messages)
                            ? html`
                                  <div
                                      class="channel-new-topic-button tippy-zulip-tooltip hidden-for-spectators auto-hide-left-sidebar-overlay"
                                      data-tippy-content="${to_bool(
                                          context.is_empty_topic_only_channel,
                                      ) || to_bool(context.cannot_create_topics_in_channel)
                                          ? $t({defaultMessage: "New message"})
                                          : $t({defaultMessage: "New topic"})}"
                                      data-stream-id="${context.id}"
                                  >
                                      <i
                                          class="channel-new-topic-icon zulip-icon zulip-icon-square-plus"
                                          aria-hidden="true"
                                      ></i>
                                  </div>
                              `
                            : ""}
                    </div>

                    <div class="stream-markers-and-unreads">
                        <span class="unread_mention_info"></span>
                        <span class="unread_count normal-count"></span>
                        <span class="masked_unread_count">
                            <i class="zulip-icon zulip-icon-masked-unread"></i>
                        </span>
                    </div>

                    <span class="sidebar-menu-icon stream-sidebar-menu-icon"
                        ><i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i
                    ></span>
                </a>
            </div>
        </li>
    `;
    return to_html(out);
}
