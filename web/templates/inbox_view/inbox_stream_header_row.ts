import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_stream_privacy from "../stream_privacy.ts";

export default function render_inbox_stream_header_row(context) {
    const out = html`<div
        id="inbox-stream-header-${context.stream_id}"
        class="inbox-header ${to_bool(context.is_hidden) ? "hidden_by_filters" : ""} ${to_bool(
            context.is_collapsed,
        )
            ? "inbox-collapsed-state"
            : ""}"
        data-col-index="${context.column_indexes.FULL_ROW}"
        tabindex="0"
        data-stream-id="${context.stream_id}"
        style="background: ${context.stream_header_color};"
    >
        <div class="inbox-focus-border">
            <div class="inbox-left-part-wrapper">
                <div class="inbox-left-part">
                    <div class="inbox-header-name">
                        <span
                            class="stream-privacy-original-color-${context.stream_id} stream-privacy filter-icon"
                            style="color: ${context.stream_color}"
                        >
                            ${{__html: render_stream_privacy(context)}}
                        </span>
                        <span class="inbox-header-name-text">${context.stream_name}</span>
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
                    <div
                        class="collapsible-button toggle-inbox-header-icon ${to_bool(
                            context.is_collapsed,
                        )
                            ? "icon-collapsed-state"
                            : ""}"
                    >
                        <i class="channel-row-chevron zulip-icon zulip-icon-chevron-down"></i>
                    </div>
                    <span
                        class="unread_mention_info tippy-zulip-tooltip
                  ${!to_bool(context.mention_in_unread) ? "hidden" : ""}"
                        data-tippy-content="${$t({defaultMessage: "You have unread mentions"})}"
                        >@</span
                    >
                    <div
                        class="unread-count-focus-outline"
                        tabindex="0"
                        data-col-index="${context.column_indexes.UNREAD_COUNT}"
                    >
                        <span
                            class="unread_count tippy-zulip-tooltip on_hover_topic_read"
                            data-stream-id="${context.stream_id}"
                            data-tippy-content="${$t({defaultMessage: "Mark as read"})}"
                            aria-label="${$t({defaultMessage: "Mark as read"})}"
                            >${context.unread_count}</span
                        >
                    </div>
                </div>
            </div>
            <div class="inbox-right-part-wrapper">
                <div class="inbox-right-part">
                    ${to_bool(context.is_muted)
                        ? html`
                              <span
                                  class="channel-visibility-policy-indicator toggle-channel-visibility tippy-zulip-tooltip"
                                  data-stream-id="${context.stream_id}"
                                  tabindex="0"
                                  data-col-index="${context.column_indexes.TOPIC_VISIBILITY}"
                                  data-tooltip-template-id="inbox-channel-mute-toggle-tooltip-template"
                              >
                                  <i
                                      class="zulip-icon zulip-icon-mute recipient_bar_icon"
                                      role="button"
                                  ></i>
                              </span>
                          `
                        : ""}
                    <div
                        class="inbox-action-button inbox-stream-menu"
                        data-stream-id="${context.stream_id}"
                        tabindex="0"
                        data-col-index="${context.column_indexes.ACTION_MENU}"
                    >
                        <i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
