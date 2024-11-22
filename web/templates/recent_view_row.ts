import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_recent_view_row(context) {
    const out = html`<tr
        id="recent_conversation:${context.conversation_key}"
        class="${to_bool(context.unread_count) ? "unread_topic" : ""} ${to_bool(context.is_private)
            ? "private_conversation_row"
            : ""}"
    >
        <td class="recent_topic_stream">
            <div class="flex_container flex_container_pm">
                <div
                    class="left_part recent_view_focusable"
                    data-col-index="${context.column_indexes.stream}"
                >
                    ${to_bool(context.is_private)
                        ? html`
                              <span class="zulip-icon zulip-icon-user"></span>
                              <a href="${context.pm_url}" class="recent-view-table-link"
                                  >${$t({defaultMessage: "Direct messages"})}</a
                              >
                          `
                        : html`
                              <span
                                  class="stream-privacy-original-color-${context.stream_id} stream-privacy filter-icon"
                                  style="color: ${context.stream_color}"
                              >
                                  ${{__html: render_stream_privacy(context)}}
                              </span>
                              <a href="${context.topic_url}" class="recent-view-table-link"
                                  >${context.stream_name}</a
                              >
                          `}
                </div>
                ${/* For presence/group indicator */ ""}${to_bool(context.is_private)
                    ? html`
                          <div class="right_part">
                              <span
                                  class="pm_status_icon ${!to_bool(context.is_group)
                                      ? "show-tooltip"
                                      : ""}"
                                  data-tippy-placement="top"
                                  data-user-ids-string="${context.user_ids_string}"
                              >
                                  ${to_bool(context.is_group)
                                      ? html`
                                            <span class="zulip-icon zulip-icon-triple-users"></span>
                                        `
                                      : to_bool(context.is_bot)
                                        ? html`
                                              <span
                                                  class="zulip-icon zulip-icon-bot"
                                                  aria-hidden="true"
                                              ></span>
                                          `
                                        : html`
                                              <span
                                                  class="${context.user_circle_class} user_circle"
                                                  data-presence-indicator-user-id="${context.user_ids_string}"
                                              ></span>
                                          `}
                              </span>
                          </div>
                      `
                    : ""}
            </div>
        </td>
        <td class="recent_topic_name" ${!to_bool(context.is_spectator) ? html` colspan="2"` : ""}>
            <div class="flex_container">
                <div
                    class="left_part recent_view_focusable line_clamp"
                    data-col-index="${context.column_indexes.topic}"
                >
                    ${to_bool(context.is_private)
                        ? html`
                              <a href="${context.pm_url}" class="recent-view-table-link"
                                  >${{__html: context.rendered_pm_with}}</a
                              >
                          `
                        : html`
                              <a
                                  class="white-space-preserve-wrap recent-view-table-link"
                                  href="${context.topic_url}"
                                  >${context.topic}</a
                              >
                          `}
                </div>
                <div class="right_part">
                    ${to_bool(context.is_private)
                        ? html`
                              <div class="recent_topic_actions">
                                  <div
                                      class="recent_view_focusable"
                                      data-col-index="${context.column_indexes.read}"
                                  >
                                      <span
                                          class="unread_count unread_count_pm recent-view-table-unread-count ${!to_bool(
                                              context.unread_count,
                                          )
                                              ? "unread_hidden"
                                              : ""} tippy-zulip-tooltip on_hover_topic_read"
                                          data-user-ids-string="${context.user_ids_string}"
                                          data-tippy-content="${$t({
                                              defaultMessage: "Mark as read",
                                          })}"
                                          role="button"
                                          tabindex="0"
                                          aria-label="${$t({defaultMessage: "Mark as read"})}"
                                          >${context.unread_count}</span
                                      >
                                  </div>
                              </div>
                              <div class="recent_topic_actions dummy_action_button">
                                  <div
                                      class="recent_view_focusable"
                                      data-col-index="${context.column_indexes.read}"
                                  >
                                      ${
                                          /* Invisible icon, used only for alignment of unread count. */ ""
                                      }
                                      <i
                                          class="zulip-icon zulip-icon-mute on_hover_topic_unmute recipient_bar_icon"
                                      ></i>
                                  </div>
                              </div>
                          `
                        : html`
                              <span
                                  class="unread_mention_info tippy-zulip-tooltip ${!to_bool(
                                      context.mention_in_unread,
                                  )
                                      ? "unread_hidden"
                                      : ""}"
                                  data-tippy-content="${$t({defaultMessage: "You have mentions"})}"
                                  >@</span
                              >
                              <div class="recent_topic_actions">
                                  <div
                                      class="recent_view_focusable hidden-for-spectators"
                                      data-col-index="${context.column_indexes.read}"
                                  >
                                      <span
                                          class="unread_count recent-view-table-unread-count ${!to_bool(
                                              context.unread_count,
                                          )
                                              ? "unread_hidden"
                                              : ""} tippy-zulip-tooltip on_hover_topic_read"
                                          data-stream-id="${context.stream_id}"
                                          data-topic-name="${context.topic}"
                                          data-tippy-content="${$t({
                                              defaultMessage: "Mark as read",
                                          })}"
                                          role="button"
                                          tabindex="0"
                                          aria-label="${$t({defaultMessage: "Mark as read"})}"
                                          >${context.unread_count}</span
                                      >
                                  </div>
                              </div>
                              <div class="recent_topic_actions">
                                  <div class="hidden-for-spectators">
                                      <span
                                          class="recent_view_focusable change_visibility_policy hidden-for-spectators"
                                          data-stream-id="${context.stream_id}"
                                          data-topic-name="${context.topic}"
                                          data-col-index="${context.column_indexes.mute}"
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
                                                        tabindex="0"
                                                        aria-haspopup="true"
                                                        aria-label="${$t({
                                                            defaultMessage:
                                                                "You follow this topic.",
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
                                  </div>
                              </div>
                          `}
                </div>
            </div>
        </td>
        <td class="recent_topic_users">
            <ul class="recent_view_participants">
                ${to_bool(context.other_senders_count)
                    ? html`
                          <li
                              class="recent_view_participant_item tippy-zulip-tooltip"
                              data-tooltip-template-id="recent_view_participant_overflow_tooltip:${context.conversation_key}"
                          >
                              <span class="recent_view_participant_overflow"
                                  >+${context.other_senders_count}</span
                              >
                          </li>
                          <template
                              id="recent_view_participant_overflow_tooltip:${context.conversation_key}"
                              >${{__html: context.other_sender_names_html}}</template
                          >
                      `
                    : ""}${to_array(context.senders).map((sender) =>
                    to_bool(sender.is_muted)
                        ? html`
                              <li
                                  class="recent_view_participant_item participant_profile tippy-zulip-tooltip"
                                  data-tippy-content="${$t({defaultMessage: "Muted user"})}"
                                  data-user-id="${sender.user_id}"
                              >
                                  <span
                                      ><i class="fa fa-user recent_view_participant_overflow"></i
                                  ></span>
                              </li>
                          `
                        : html`
                              <li
                                  class="recent_view_participant_item participant_profile tippy-zulip-tooltip"
                                  data-tippy-content="${sender.full_name}"
                                  data-user-id="${sender.user_id}"
                              >
                                  <img
                                      src="${sender.avatar_url_small}"
                                      class="recent_view_participant_avatar"
                                  />
                              </li>
                          `,
                )}
            </ul>
        </td>
        <td class="recent_topic_timestamp">
            <div
                class="last_msg_time tippy-zulip-tooltip"
                data-tippy-content="${context.full_last_msg_date_time}"
            >
                <a href="${context.last_msg_url}" tabindex="-1">${context.last_msg_time}</a>
            </div>
        </td>
    </tr> `;
    return to_html(out);
}
