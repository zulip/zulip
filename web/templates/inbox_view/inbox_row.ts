import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_inbox_stream_header_row from "./inbox_stream_header_row.ts";

export default function render_inbox_row(context) {
    const out = to_bool(context.is_stream)
        ? html` ${{__html: render_inbox_stream_header_row(context)}}`
        : html`
              <div
                  id="inbox-row-conversation-${context.conversation_key}"
                  class="inbox-row ${to_bool(context.is_hidden)
                      ? "hidden_by_filters"
                      : ""} ${to_bool(context.is_collapsed) ? "collapsed_container" : ""}"
                  tabindex="0"
                  data-col-index="${context.column_indexes.RECIPIENT}"
              >
                  <div class="inbox-focus-border">
                      <div class="inbox-left-part-wrapper">
                          <div class="inbox-left-part">
                              <div
                                  class="hide fake-collapse-button"
                                  tabindex="0"
                                  data-col-index="${context.column_indexes.COLLAPSE_BUTTON}"
                              ></div>
                              ${to_bool(context.is_direct)
                                  ? html`
                                        <a
                                            class="recipients_info ${!to_bool(
                                                context.user_circle_class,
                                            )
                                                ? "inbox-group-or-bot-dm"
                                                : ""}"
                                            href="${context.dm_url}"
                                            tabindex="-1"
                                        >
                                            <span class="user_block">
                                                ${to_bool(context.is_bot)
                                                    ? html`
                                                          <span
                                                              class="zulip-icon zulip-icon-bot"
                                                              aria-hidden="true"
                                                          ></span>
                                                      `
                                                    : to_bool(context.is_group)
                                                      ? html`
                                                            <span
                                                                class="zulip-icon zulip-icon-triple-users"
                                                                aria-hidden="true"
                                                            ></span>
                                                        `
                                                      : html`
                                                            <span
                                                                class="${context.user_circle_class} user_circle"
                                                                data-presence-indicator-user-id="${context.user_ids_string}"
                                                            ></span>
                                                        `}
                                                <span class="recipients_name"
                                                    >${{__html: context.rendered_dm_with}}</span
                                                >
                                            </span>
                                        </a>
                                        <div
                                            class="unread-count-focus-outline"
                                            tabindex="0"
                                            data-col-index="${context.column_indexes.UNREAD_COUNT}"
                                        >
                                            <span
                                                class="unread_count tippy-zulip-tooltip on_hover_dm_read"
                                                data-user-ids-string="${context.user_ids_string}"
                                                data-tippy-content="${$t({
                                                    defaultMessage: "Mark as read",
                                                })}"
                                                aria-label="${$t({defaultMessage: "Mark as read"})}"
                                                >${context.unread_count}</span
                                            >
                                        </div>
                                    `
                                  : to_bool(context.is_topic)
                                    ? /* Invisible user circle element for alignment of topic text with DM user name */ html`
                                          <span
                                              class="user_circle_green user_circle invisible"
                                          ></span>
                                          <div class="inbox-topic-name">
                                              <a tabindex="-1" href="${context.topic_url}"
                                                  >${context.topic_name}</a
                                              >
                                          </div>
                                          <span
                                              class="unread_mention_info tippy-zulip-tooltip
                          ${!to_bool(context.mention_in_unread) ? "hidden" : ""}"
                                              data-tippy-content="${$t({
                                                  defaultMessage: "You have mentions",
                                              })}"
                                              >@</span
                                          >
                                          <div
                                              class="unread-count-focus-outline"
                                              tabindex="0"
                                              data-col-index="${context.column_indexes
                                                  .UNREAD_COUNT}"
                                          >
                                              <span
                                                  class="unread_count tippy-zulip-tooltip on_hover_topic_read"
                                                  data-stream-id="${context.stream_id}"
                                                  data-topic-name="${context.topic_name}"
                                                  data-tippy-content="${$t({
                                                      defaultMessage: "Mark as read",
                                                  })}"
                                                  aria-label="${$t({
                                                      defaultMessage: "Mark as read",
                                                  })}"
                                              >
                                                  ${context.unread_count}
                                              </span>
                                          </div>
                                      `
                                    : ""}
                          </div>
                      </div>
                      ${!to_bool(context.is_direct)
                          ? html`
                                <div class="inbox-right-part-wrapper">
                                    <div class="inbox-right-part">
                                        ${to_bool(context.is_topic)
                                            ? html`
                                                  <span
                                                      class="visibility-policy-indicator change_visibility_policy hidden-for-spectators${context.visibility_policy ===
                                                      context.all_visibility_policies.INHERIT
                                                          ? " inbox-row-visibility-policy-inherit"
                                                          : ""}"
                                                      data-stream-id="${context.stream_id}"
                                                      data-topic-name="${context.topic_name}"
                                                      tabindex="0"
                                                      data-col-index="${context.column_indexes
                                                          .TOPIC_VISIBILITY}"
                                                  >
                                                      ${context.visibility_policy ===
                                                      context.all_visibility_policies.FOLLOWED
                                                          ? html`
                                                                <i
                                                                    class="zulip-icon zulip-icon-follow recipient_bar_icon"
                                                                    data-tippy-content="${$t({
                                                                        defaultMessage:
                                                                            "You follow this topic.",
                                                                    })}"
                                                                    role="button"
                                                                    aria-haspopup="true"
                                                                    aria-label="${$t({
                                                                        defaultMessage:
                                                                            "You follow this topic.",
                                                                    })}"
                                                                ></i>
                                                            `
                                                          : context.visibility_policy ===
                                                              context.all_visibility_policies
                                                                  .UNMUTED
                                                            ? html`
                                                                  <i
                                                                      class="zulip-icon zulip-icon-unmute-new recipient_bar_icon"
                                                                      data-tippy-content="${$t({
                                                                          defaultMessage:
                                                                              "You have unmuted this topic.",
                                                                      })}"
                                                                      role="button"
                                                                      aria-haspopup="true"
                                                                      aria-label="${$t({
                                                                          defaultMessage:
                                                                              "You have unmuted this topic.",
                                                                      })}"
                                                                  ></i>
                                                              `
                                                            : context.visibility_policy ===
                                                                context.all_visibility_policies
                                                                    .MUTED
                                                              ? html`
                                                                    <i
                                                                        class="zulip-icon zulip-icon-mute-new recipient_bar_icon"
                                                                        data-tippy-content="${$t({
                                                                            defaultMessage:
                                                                                "You have muted this topic.",
                                                                        })}"
                                                                        role="button"
                                                                        aria-haspopup="true"
                                                                        aria-label="${$t({
                                                                            defaultMessage:
                                                                                "You have muted this topic.",
                                                                        })}"
                                                                    ></i>
                                                                `
                                                              : context.visibility_policy ===
                                                                  context.all_visibility_policies
                                                                      .INHERIT
                                                                ? html`
                                                                      <i
                                                                          class="zulip-icon zulip-icon-inherit recipient_bar_icon"
                                                                          role="button"
                                                                          aria-haspopup="true"
                                                                          aria-label="${$t({
                                                                              defaultMessage:
                                                                                  "Notifications are based on your configuration for this channel.",
                                                                          })}"
                                                                      ></i>
                                                                  `
                                                                : ""}
                                                  </span>
                                              `
                                            : ""}
                                        <div
                                            class="inbox-action-button inbox-topic-menu"
                                            ${to_bool(context.is_topic)
                                                ? html`data-stream-id="${context.stream_id}"
                                                  data-topic-name="${context.topic_name}"
                                                  data-topic-url="${context.topic_url}"`
                                                : ""}
                                            tabindex="0"
                                            data-col-index="${context.column_indexes.ACTION_MENU}"
                                        >
                                            <i
                                                class="zulip-icon zulip-icon-more-vertical"
                                                aria-hidden="true"
                                            ></i>
                                        </div>
                                    </div>
                                </div>
                            `
                          : ""}
                  </div>
              </div>
          `;
    return to_html(out);
}
