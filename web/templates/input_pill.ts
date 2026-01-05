import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_status_emoji from "./status_emoji.ts";

export default function render_input_pill(context) {
    const out = html`<div
        class="pill ${to_bool(context.deactivated) ? " deactivated-pill " : ""}"
        ${to_bool(context.user_id) ? html`data-user-id="${context.user_id}"` : ""}${to_bool(
            context.group_id,
        )
            ? html`data-user-group-id="${context.group_id}"`
            : ""}${to_bool(context.stream_id)
            ? html`data-stream-id="${context.stream_id}"`
            : ""}${to_bool(context.data_syntax) ? html`data-syntax="${context.data_syntax}"` : ""}
        tabindex="0"
    >
        ${to_bool(context.has_image)
            ? html` <img class="pill-image" src="${context.img_src}" />
                  <div class="pill-image-border"></div>
                  ${to_bool(context.deactivated)
                      ? html` <span class="fa fa-ban slashed-circle-icon"></span> `
                      : ""}`
            : ""}
        <span class="pill-label">
            <span class="pill-value">
                ${to_bool(context.has_stream)
                    ? to_bool(context.stream.invite_only)
                        ? html`<i
                              class="zulip-icon zulip-icon-lock channel-privacy-type-icon"
                              aria-hidden="true"
                          ></i>`
                        : to_bool(context.stream.is_web_public)
                          ? html`<i
                                class="zulip-icon zulip-icon-globe channel-privacy-type-icon"
                                aria-hidden="true"
                            ></i>`
                          : html`<i
                                class="zulip-icon zulip-icon-hashtag channel-privacy-type-icon"
                                aria-hidden="true"
                            ></i>`
                    : ""}${to_bool(context.is_empty_string_topic)
                    ? html`
                          ${context.sign}topic:${to_bool(context.topic_display_name)
                              ? html`<span class="empty-topic-display">
                                    ${context.topic_display_name}</span
                                >`
                              : ""}
                      `
                    : html` ${context.display_value} `} </span
            >${to_bool(context.should_add_guest_user_indicator)
                ? html`&nbsp;<i>(${$t({defaultMessage: "guest"})})</i>`
                : ""}${to_bool(context.has_status)
                ? {__html: render_status_emoji(context.status_emoji_info)}
                : ""}${to_bool(context.is_bot)
                ? html`<i
                      class="zulip-icon zulip-icon-bot"
                      aria-label="${$t({defaultMessage: "Bot"})}"
                  ></i>`
                : ""}${to_bool(context.show_group_members_count)
                ? html`&nbsp;<span class="group-members-count"
                          >(${context.group_members_count})</span
                      >`
                : ""}</span
        >
        ${to_bool(context.show_expand_button)
            ? html`
                  <div class="expand">
                      <a
                          role="button"
                          class="zulip-icon zulip-icon-expand-both-diagonals pill-expand-button"
                      ></a>
                  </div>
              `
            : ""}${!to_bool(context.disabled)
            ? html`
                  <div class="exit">
                      <a role="button" class="zulip-icon zulip-icon-close pill-close-button"></a>
                  </div>
              `
            : ""}
    </div> `;
    return to_html(out);
}
