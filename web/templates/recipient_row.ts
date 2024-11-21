import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_recipient_row(context) {
    const out = to_bool(context.is_stream)
        ? html`<div
              class="message_header message_header_stream right_part"
              data-stream-id="${context.stream_id}"
              data-topic-name="${context.topic}"
          >
              <div
                  class="message-header-contents"
                  style="background: ${context.recipient_bar_color};"
              >
                  ${/* stream link */ ""}
                  <a
                      class="message_label_clickable narrows_by_recipient stream_label tippy-narrow-tooltip"
                      href="${context.stream_url}"
                      draggable="false"
                      data-tippy-content="${$t(
                          {defaultMessage: "Go to #{display_recipient}"},
                          {display_recipient: context.display_recipient},
                      )}"
                  >
                      <span
                          class="stream-privacy-modified-color-${context.stream_id} stream-privacy filter-icon"
                          style="color: ${context.stream_privacy_icon_color}"
                      >
                          ${{__html: render_stream_privacy(context)}} </span
                      >${/* Recipient (e.g. stream/topic or topic) */ ""}<span
                          class="message-header-stream-name"
                          >${context.display_recipient}</span
                      >
                      ${to_bool(context.is_archived)
                          ? html`
                                <span class="message-header-stream-archived"
                                    ><i class="archived-indicator"
                                        >(${$t({defaultMessage: "archived"})})</i
                                    ></span
                                >
                            `
                          : ""}
                  </a>
                  <span class="stream_topic_separator"
                      ><i class="zulip-icon zulip-icon-chevron-right"></i
                  ></span>

                  ${/* hidden narrow icon for copy-pasting */ ""}
                  <span class="copy-paste-text">&gt;</span>

                  ${/* topic stuff */ ""}
                  <span class="stream_topic">
                      ${/* topic link */ ""}
                      <a
                          class="message_label_clickable narrows_by_topic tippy-narrow-tooltip"
                          draggable="false"
                          href="${context.topic_url}"
                          data-tippy-content="${$t(
                              {defaultMessage: "Go to #{display_recipient} > {topic_display_name}"},
                              {
                                  display_recipient: context.display_recipient,
                                  topic_display_name: context.topic_display_name,
                              },
                          )}"
                      >
                          ${to_bool(context.use_match_properties) &&
                          !to_bool(context.is_empty_string_topic)
                              ? html`
                                    <span class="stream-topic-inner"
                                        >${{__html: context.match_topic_html}}</span
                                    >
                                `
                              : html`
                                    <span
                                        class="stream-topic-inner ${to_bool(
                                            context.is_empty_string_topic,
                                        )
                                            ? "empty-topic-display"
                                            : ""}"
                                        >${context.topic_display_name}</span
                                    >
                                `}
                      </a>
                  </span>
                  <span class="recipient_bar_controls no-select">
                      <span class="topic_edit hidden-for-spectators"></span>

                      ${/* exterior links (e.g. to a trac ticket) */ ""}${to_array(
                          context.topic_links,
                      ).map((link) =>
                          ((
                              context2,
                          ) => /* TODO: Find a way to use the icon_button component with <a> tags,
                    instead of copying over the icon button styles via the utility classes. */ html`
                              <a
                                  href="${context2.url}"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="recipient-bar-control recipient-bar-control-icon no-underline icon-button icon-button-neutral"
                                  data-tippy-content="${$t(
                                      {defaultMessage: "Open {text}"},
                                      {text: context2.text},
                                  )}"
                                  aria-label="${$t(
                                      {defaultMessage: "Open {text}"},
                                      {text: context2.text},
                                  )}"
                                  tabindex="0"
                              >
                                  <i
                                      class="zulip-icon zulip-icon-external-link"
                                      aria-hidden="true"
                                  ></i>
                              </a>
                          `)(link),
                      )}
                      ${/* edit topic pencil icon */ ""}${to_bool(context.is_topic_editable)
                          ? html` ${{
                                __html: render_icon_button({
                                    ["aria-label"]: $t({defaultMessage: "Edit topic"}),
                                    ["data-tippy-content"]: $t({defaultMessage: "Edit topic"}),
                                    custom_classes:
                                        "on_hover_topic_edit recipient-bar-control recipient-bar-control-icon hidden-for-spectators",
                                    intent: "neutral",
                                    icon: "pencil",
                                }),
                            }}`
                          : ""}
                      ${to_bool(context.user_can_resolve_topic) &&
                      !to_bool(context.is_empty_string_topic)
                          ? to_bool(context.topic_is_resolved)
                              ? html` ${{
                                    __html: render_icon_button({
                                        custom_classes:
                                            "recipient-bar-control on-hover-unresolve-loading-indicator hidden-for-spectators hide",
                                        intent: "neutral",
                                        icon: "placeholder",
                                    }),
                                }}`
                              : html` ${{
                                    __html: render_icon_button({
                                        ["aria-label"]: $t({defaultMessage: "Mark as resolved"}),
                                        ["data-tippy-content"]: $t({
                                            defaultMessage: "Mark as resolved",
                                        }),
                                        custom_classes:
                                            "on_hover_topic_resolve recipient-bar-control recipient-bar-control-icon hidden-for-spectators",
                                        intent: "neutral",
                                        icon: "check",
                                    }),
                                }}`
                          : ""}
                      ${/* visibility policy menu */ ""}${to_bool(context.is_subscribed) &&
                      !to_bool(context.is_archived)
                          ? /* We define the change_visibility_policy class in a wrapper span
            since the icon button component already has a tippy tooltip attached
            to it and Tippy does not support multiple tooltips on a single element. */ html`
                                <span
                                    class="change_visibility_policy recipient-bar-control hidden-for-spectators"
                                    aria-haspopup="true"
                                >
                                    ${context.visibility_policy ===
                                    context.all_visibility_policies.FOLLOWED
                                        ? html` ${{
                                              __html: render_icon_button({
                                                  ["aria-label"]: $t({
                                                      defaultMessage: "You follow this topic.",
                                                  }),
                                                  ["data-tippy-content"]: $t({
                                                      defaultMessage: "You follow this topic.",
                                                  }),
                                                  custom_classes: "recipient-bar-control-icon",
                                                  intent: "neutral",
                                                  icon: "follow",
                                              }),
                                          }}`
                                        : context.visibility_policy ===
                                            context.all_visibility_policies.UNMUTED
                                          ? html` ${{
                                                __html: render_icon_button({
                                                    ["aria-label"]: $t({
                                                        defaultMessage:
                                                            "You have unmuted this topic.",
                                                    }),
                                                    ["data-tippy-content"]: $t({
                                                        defaultMessage:
                                                            "You have unmuted this topic.",
                                                    }),
                                                    custom_classes:
                                                        "recipient-bar-control recipient-bar-control-icon",
                                                    intent: "neutral",
                                                    icon: "unmute",
                                                }),
                                            }}`
                                          : context.visibility_policy ===
                                              context.all_visibility_policies.MUTED
                                            ? html` ${{
                                                  __html: render_icon_button({
                                                      ["aria-label"]: $t({
                                                          defaultMessage:
                                                              "You have muted this topic.",
                                                      }),
                                                      ["data-tippy-content"]: $t({
                                                          defaultMessage:
                                                              "You have muted this topic.",
                                                      }),
                                                      custom_classes: "recipient-bar-control-icon",
                                                      intent: "neutral",
                                                      icon: "mute",
                                                  }),
                                              }}`
                                            : html`
                                                  ${{
                                                      __html: render_icon_button({
                                                          ["aria-label"]: $t({
                                                              defaultMessage:
                                                                  "Notifications are based on your configuration for this channel.",
                                                          }),
                                                          ["data-tippy-content"]: $t({
                                                              defaultMessage:
                                                                  "Notifications are based on your configuration for this channel.",
                                                          }),
                                                          custom_classes:
                                                              "recipient-bar-control-icon",
                                                          intent: "neutral",
                                                          icon: "inherit",
                                                      }),
                                                  }}
                                              `}
                                </span>
                            `
                          : ""}
                      ${/* Topic menu */ ""}${
                          /* We define the recipient-row-topic-menu class in a wrapper span
            since the icon button component already has a tippy tooltip attached
            to it and attaching the topic actions menu popover to it causes buggy behavior. */ ""
                      }
                      <span
                          class="recipient-row-topic-menu recipient-bar-control"
                          aria-haspopup="true"
                      >
                          ${{
                              __html: render_icon_button({
                                  ["aria-label"]: $t({defaultMessage: "Topic actions"}),
                                  ["data-tippy-content"]: $t({defaultMessage: "Topic actions"}),
                                  custom_classes: "recipient-bar-control-icon",
                                  intent: "neutral",
                                  icon: "more-vertical",
                              }),
                          }}
                      </span>
                  </span>
                  <span
                      class="recipient_row_date ${!to_bool(context.always_display_date) &&
                      to_bool(context.date_unchanged)
                          ? "recipient_row_date_unchanged"
                          : ""}"
                      >${{__html: context.date_html}}</span
                  >
              </div>
          </div> `
        : html`<div class="message_header message_header_private_message">
              <div class="message-header-contents">
                  <a
                      class="message_label_clickable narrows_by_recipient stream_label tippy-narrow-tooltip"
                      href="${context.pm_with_url}"
                      draggable="false"
                      data-tippy-content="${to_bool(context.is_dm_with_self)
                          ? $t({defaultMessage: "Go to direct messages with yourself"})
                          : $t(
                                {
                                    defaultMessage:
                                        "Go to direct messages with {display_reply_to_for_tooltip}",
                                },
                                {
                                    display_reply_to_for_tooltip:
                                        context.display_reply_to_for_tooltip,
                                },
                            )}"
                  >
                      <span class="private_message_header_icon"
                          ><i class="zulip-icon zulip-icon-user"></i
                      ></span>
                      <span class="private_message_header_name">
                          ${to_bool(context.is_dm_with_self)
                              ? html` ${$t({defaultMessage: "Messages with yourself"})} `
                              : $html_t(
                                    {defaultMessage: "You and <z-user-names></z-user-names>"},
                                    {
                                        ["z-user-names"]: () =>
                                            to_array(context.recipient_users).map(
                                                (user, user_index, user_array) =>
                                                    html`${user.full_name}${to_bool(user.is_bot)
                                                        ? html`<i
                                                              class="zulip-icon zulip-icon-bot"
                                                              aria-label="${$t({
                                                                  defaultMessage: "Bot",
                                                              })}"
                                                          ></i>`
                                                        : ""}${to_bool(
                                                        user.should_add_guest_user_indicator,
                                                    )
                                                        ? html`&nbsp;<i
                                                                  >(${$t({
                                                                      defaultMessage: "guest",
                                                                  })})</i
                                                              >`
                                                        : ""}${user_index !== user_array.length - 1
                                                        ? ", "
                                                        : ""} `,
                                            ),
                                    },
                                )}
                      </span>
                  </a>
                  <span
                      class="recipient_row_date ${!to_bool(context.always_display_date) &&
                      to_bool(context.date_unchanged)
                          ? "recipient_row_date_unchanged"
                          : ""}"
                      >${{__html: context.date_html}}</span
                  >
              </div>
          </div> `;
    return to_html(out);
}
