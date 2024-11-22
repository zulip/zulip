import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_stream_privacy from "../stream_privacy.ts";

export default function render_inbox_stream_header_row(context) {
    const out = html`<div
        id="inbox-stream-header-${context.stream_id}"
        class="inbox-header ${to_bool(context.is_hidden) ? "hidden_by_filters" : ""}"
        tabindex="0"
        data-stream-id="${context.stream_id}"
        style="background: ${context.stream_header_color};"
    >
        <div class="inbox-focus-border">
            <div class="inbox-left-part-wrapper">
                <div class="collapsible-button">
                    <i
                        class="zulip-icon zulip-icon-arrow-down toggle-inbox-header-icon ${to_bool(
                            context.is_collapsed,
                        )
                            ? "icon-collapsed-state"
                            : ""}"
                    ></i>
                </div>
                <div class="inbox-left-part">
                    <div tabindex="0" class="inbox-header-name">
                        <div class="inbox-header-name-focus-border">
                            <span
                                class="stream-privacy-original-color-${context.stream_id} stream-privacy filter-icon"
                                style="color: ${context.stream_color}"
                            >
                                ${{__html: render_stream_privacy(context)}}
                            </span>
                            <a tabindex="-1" href="${context.stream_url}">${context.stream_name}</a>
                            ${to_bool(context.is_archived)
                                ? html`
                                      <span class="inbox-header-stream-archived">
                                          <i class="archived-indicator"
                                              >(${$t({defaultMessage: "archived"})})</i
                                          >
                                      </span>
                                  `
                                : ""}
                        </div>
                    </div>
                    <span
                        class="unread_mention_info tippy-zulip-tooltip
                  ${!to_bool(context.mention_in_unread) ? "hidden" : ""}"
                        data-tippy-content="${$t({defaultMessage: "You have mentions"})}"
                        >@</span
                    >
                    <div class="unread-count-focus-outline" tabindex="0">
                        <span
                            class="unread_count tippy-zulip-tooltip on_hover_topic_read"
                            data-stream-id="${context.stream_id}"
                            data-tippy-content="${$t({defaultMessage: "Mark as read"})}"
                            aria-label="${$t({defaultMessage: "Mark as read"})}"
                            >${context.unread_count}</span
                        >
                    </div>
                    <div class="topic-visibility-indicator invisible" tabindex="0"></div>
                </div>
            </div>
            <div class="inbox-right-part-wrapper">
                <div class="inbox-right-part">
                    <div
                        class="inbox-action-button inbox-stream-menu"
                        data-stream-id="${context.stream_id}"
                        tabindex="0"
                    >
                        <i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
