import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_recipient_row(context) {
    const out = to_bool(context.is_stream)
        ? html`<div
              class="message_header message_header_stream right_part"
              data-stream-id="${context.stream_id}"
          >
              <div
                  class="message-header-contents"
                  style="background: ${context.recipient_bar_color};"
              >
                  ${/* stream link */ ""}
                  <a
                      class="message_label_clickable narrows_by_recipient stream_label tippy-narrow-tooltip"
                      href="${context.stream_url}"
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
                          href="${context.topic_url}"
                          data-tippy-content="${$t(
                              {defaultMessage: "Go to #{display_recipient} > {topic}"},
                              {display_recipient: context.display_recipient, topic: context.topic},
                          )}"
                      >
                          ${to_bool(context.use_match_properties)
                              ? html`
                                    <span class="stream-topic-inner"
                                        >${{__html: context.match_topic}}</span
                                    >
                                `
                              : html` <span class="stream-topic-inner">${context.topic}</span> `}
                      </a>
                  </span>
                  <span class="recipient_bar_controls no-select">
                      <span class="topic_edit hidden-for-spectators">
                          <span class="topic_edit_form"></span>
                      </span>

                      ${/* exterior links (e.g. to a trac ticket) */ ""}${to_array(
                          context.topic_links,
                      ).map(
                          (link) => html`
                              <a
                                  href="${link.url}"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="external-topic-link no-underline"
                              >
                                  <i
                                      class="fa fa-external-link-square recipient_bar_icon"
                                      data-tippy-content="Open ${link.text}"
                                      aria-label="${$t({defaultMessage: "External link"})}"
                                  ></i>
                              </a>
                          `,
                      )}
                      ${/* edit topic pencil icon */ ""}${to_bool(context.always_visible_topic_edit)
                          ? html`
                                <i
                                    class="fa fa-pencil always_visible_topic_edit recipient_bar_icon hidden-for-spectators"
                                    data-tippy-content="${$t({defaultMessage: "Edit topic"})}"
                                    role="button"
                                    tabindex="0"
                                    aria-label="${$t({defaultMessage: "Edit topic"})}"
                                ></i>
                            `
                          : to_bool(context.on_hover_topic_edit)
                            ? html`
                                  <i
                                      class="fa fa-pencil on_hover_topic_edit recipient_bar_icon hidden-for-spectators"
                                      data-tippy-content="${$t({defaultMessage: "Edit topic"})}"
                                      role="button"
                                      tabindex="0"
                                      aria-label="${$t({defaultMessage: "Edit topic"})}"
                                  ></i>
                              `
                            : ""}
                      ${to_bool(context.user_can_resolve_topic)
                          ? html`${to_bool(context.topic_is_resolved)
                                    ? html`
                                          <i
                                              class="fa fa-check on_hover_topic_unresolve recipient_bar_icon hidden-for-spectators"
                                              data-topic-name="${context.topic}"
                                              data-tippy-content="${$t({
                                                  defaultMessage: "Mark as unresolved",
                                              })}"
                                              role="button"
                                              tabindex="0"
                                              aria-label="${$t({
                                                  defaultMessage: "Mark as unresolved",
                                              })}"
                                          ></i>
                                      `
                                    : html`
                                          <i
                                              class="fa fa-check on_hover_topic_resolve recipient_bar_icon hidden-for-spectators"
                                              data-topic-name="${context.topic}"
                                              data-tippy-content="${$t({
                                                  defaultMessage: "Mark as resolved",
                                              })}"
                                              role="button"
                                              tabindex="0"
                                              aria-label="${$t({
                                                  defaultMessage: "Mark as resolved",
                                              })}"
                                          ></i>
                                      `}
                                <div
                                    class="toggle_resolve_topic_spinner"
                                    style="display: none"
                                ></div> `
                          : ""}
                      ${to_bool(context.is_subscribed)
                          ? html`
                                <span
                                    class="change_visibility_policy hidden-for-spectators"
                                    data-stream-id="${context.stream_id}"
                                    data-topic-name="${context.topic}"
                                >
                                    ${context.visibility_policy ===
                                    context.all_visibility_policies.FOLLOWED
                                        ? html`
                                              <i
                                                  class="zulip-icon zulip-icon-follow recipient_bar_icon"
                                                  data-tippy-content="${$t({
                                                      defaultMessage: "You follow this topic.",
                                                  })}"
                                                  role="button"
                                                  tabindex="0"
                                                  aria-haspopup="true"
                                                  aria-label="${$t({
                                                      defaultMessage: "You follow this topic.",
                                                  })}"
                                              ></i>
                                          `
                                        : context.visibility_policy ===
                                            context.all_visibility_policies.UNMUTED
                                          ? html`
                                                <i
                                                    class="zulip-icon zulip-icon-unmute-new recipient_bar_icon"
                                                    data-tippy-content="${$t({
                                                        defaultMessage:
                                                            "You have unmuted this topic.",
                                                    })}"
                                                    role="button"
                                                    tabindex="0"
                                                    aria-haspopup="true"
                                                    aria-label="${$t({
                                                        defaultMessage:
                                                            "You have unmuted this topic.",
                                                    })}"
                                                ></i>
                                            `
                                          : context.visibility_policy ===
                                              context.all_visibility_policies.MUTED
                                            ? html`
                                                  <i
                                                      class="zulip-icon zulip-icon-mute-new recipient_bar_icon"
                                                      data-tippy-content="${$t({
                                                          defaultMessage:
                                                              "You have muted this topic.",
                                                      })}"
                                                      role="button"
                                                      tabindex="0"
                                                      aria-haspopup="true"
                                                      aria-label="${$t({
                                                          defaultMessage:
                                                              "You have muted this topic.",
                                                      })}"
                                                  ></i>
                                              `
                                            : html`
                                                  <i
                                                      class="zulip-icon zulip-icon-inherit recipient_bar_icon"
                                                      role="button"
                                                      tabindex="0"
                                                      aria-haspopup="true"
                                                      aria-label="${$t({
                                                          defaultMessage:
                                                              "Notifications are based on your configuration for this channel.",
                                                      })}"
                                                  ></i>
                                              `}
                                </span>
                            `
                          : ""}
                  </span>
                  <span
                      class="recipient_row_date ${!to_bool(context.always_display_date) &&
                      to_bool(context.date_unchanged)
                          ? "recipient_row_date_unchanged"
                          : ""}"
                      >${{__html: context.date}}</span
                  >
              </div>
          </div> `
        : html`<div class="message_header message_header_private_message">
              <div class="message-header-contents">
                  <a
                      class="message_label_clickable narrows_by_recipient stream_label tippy-narrow-tooltip"
                      href="${context.pm_with_url}"
                      data-tippy-content="${$t(
                          {
                              defaultMessage:
                                  "Go to direct messages with {display_reply_to_for_tooltip}",
                          },
                          {display_reply_to_for_tooltip: context.display_reply_to_for_tooltip},
                      )}"
                  >
                      <span class="private_message_header_icon"
                          ><i class="zulip-icon zulip-icon-user"></i
                      ></span>
                      <span class="private_message_header_name"
                          >${$html_t(
                              {defaultMessage: "You and <z-user-names></z-user-names>"},
                              {
                                  ["z-user-names"]: () =>
                                      to_array(context.recipient_users).map(
                                          (user, user_index, user_array) =>
                                              html`${user.full_name}${to_bool(
                                                  user.should_add_guest_user_indicator,
                                              )
                                                  ? html`&nbsp;<i
                                                            >(${$t({defaultMessage: "guest"})})</i
                                                        >`
                                                  : ""}${user_index !== user_array.length - 1
                                                  ? ", "
                                                  : ""}`,
                                      ),
                              },
                          )}</span
                      >
                  </a>
                  <span
                      class="recipient_row_date ${!to_bool(context.always_display_date) &&
                      to_bool(context.date_unchanged)
                          ? "recipient_row_date_unchanged"
                          : ""}"
                      >${{__html: context.date}}</span
                  >
              </div>
          </div> `;
    return to_html(out);
}
