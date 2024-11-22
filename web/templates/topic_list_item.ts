import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_topic_list_item(context) {
    const out = html`<li
        class="bottom_left_row ${to_bool(context.is_active_topic)
            ? "active-sub-filter"
            : ""} ${to_bool(context.is_zero) ? "zero-topic-unreads" : ""} ${to_bool(
            context.is_muted,
        )
            ? "muted_topic"
            : ""} ${to_bool(context.is_unmuted_or_followed)
            ? "unmuted_or_followed_topic"
            : ""} topic-list-item"
        data-topic-name="${context.topic_name}"
    >
        <div class="topic-box">
            <span class="sidebar-topic-check"> ${context.topic_resolved_prefix} </span>
            <a href="${context.url}" class="sidebar-topic-name">
                <span class="sidebar-topic-name-inner">${context.topic_display_name}</span>
            </a>
            <div
                class="topic-markers-and-unreads change_visibility_policy"
                data-stream-id="${context.stream_id}"
                data-topic-name="${context.topic_name}"
            >
                ${to_bool(context.contains_unread_mention)
                    ? html` <span class="unread_mention_info"> @ </span> `
                    : to_bool(context.is_followed)
                      ? html`
                            <i
                                class="zulip-icon zulip-icon-follow visibility-policy-icon"
                                role="button"
                                aria-hidden="true"
                                data-tippy-content="${$t({
                                    defaultMessage: "You follow this topic.",
                                })}"
                            ></i>
                        `
                      : ""}
                <span class="unread_count ${to_bool(context.is_zero) ? "zero_count" : ""}">
                    ${context.unread}
                </span>
            </div>
            <span class="sidebar-menu-icon topic-sidebar-menu-icon">
                <i class="zulip-icon zulip-icon-more-vertical" aria-hidden="true"></i>
            </span>
        </div>
    </li> `;
    return to_html(out);
}
