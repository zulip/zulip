import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_stream_sidebar_row(context) {
    const out = /* Stream sidebar rows */ html`
        <li
            class="narrow-filter${to_bool(context.is_muted) ? " out_of_home_view" : ""}"
            data-stream-id="${context.id}"
        >
            <div class="bottom_left_row">
                <div
                    class="subscription_block selectable_sidebar_block ${to_bool(
                        context.hide_unread_count,
                    )
                        ? "hide_unread_counts"
                        : ""}"
                >
                    <span
                        class="stream-privacy-original-color-${context.id} stream-privacy filter-icon"
                        style="color: ${context.color}"
                    >
                        ${{__html: render_stream_privacy(context)}}
                    </span>

                    <a href="${context.url}" class="stream-name">${context.name}</a>

                    <div class="left-sidebar-controls">
                        ${to_bool(context.can_post_messages)
                            ? html`
                                  <div
                                      class="channel-new-topic-button tippy-zulip-tooltip hidden-for-spectators"
                                      data-tippy-content="${$t({defaultMessage: "New topic"})}"
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
                        <span class="unread_count"></span>
                        <span class="masked_unread_count">
                            <i class="zulip-icon zulip-icon-masked-unread"></i>
                        </span>
                    </div>

                    <span class="sidebar-menu-icon stream-sidebar-menu-icon"
                        ><i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i
                    ></span>
                </div>
            </div>
        </li>
    `;
    return to_html(out);
}
