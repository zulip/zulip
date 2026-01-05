import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_icon_button from "./components/icon_button.ts";
import render_scheduled_message_stream_pm_common from "./scheduled_message_stream_pm_common.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_scheduled_message(context) {
    const out = to_array(context.scheduled_messages_data).map(
        (scheduled_message) => html`
            <div
                class="scheduled-message-row overlay-message-row"
                data-scheduled-message-id="${scheduled_message.scheduled_message_id}"
            >
                <div class="scheduled-message-info-box overlay-message-info-box" tabindex="0">
                    ${to_bool(scheduled_message.is_stream)
                        ? html`
                              <div
                                  class="message_header message_header_stream restore-overlay-message overlay-message-header"
                              >
                                  <div
                                      class="message-header-contents"
                                      style="background: ${scheduled_message.recipient_bar_color};"
                                  >
                                      <div class="message_label_clickable stream_label">
                                          <span
                                              class="stream-privacy-modified-color-${scheduled_message.stream_id} stream-privacy filter-icon"
                                              style="color: ${scheduled_message.stream_privacy_icon_color}"
                                          >
                                              ${{__html: render_stream_privacy(scheduled_message)}}
                                          </span>
                                          ${scheduled_message.stream_name}
                                      </div>
                                      <span class="stream_topic_separator"
                                          ><i class="zulip-icon zulip-icon-chevron-right"></i
                                      ></span>
                                      <span class="stream_topic">
                                          <span class="message_label_clickable narrows_by_topic">
                                              <span
                                                  ${to_bool(scheduled_message.is_empty_string_topic)
                                                      ? html`class="empty-topic-display"`
                                                      : ""}
                                                  >${scheduled_message.topic_display_name}</span
                                              >
                                          </span>
                                      </span>
                                      <span class="recipient_bar_controls"></span>
                                      ${{
                                          __html: render_scheduled_message_stream_pm_common(
                                              scheduled_message,
                                          ),
                                      }}
                                  </div>
                              </div>
                          `
                        : html`
                              <div
                                  class="message_header message_header_private_message restore-overlay-message overlay-message-header"
                              >
                                  <div class="message-header-contents">
                                      <div class="message_label_clickable stream_label">
                                          <span class="private_message_header_icon"
                                              ><i class="zulip-icon zulip-icon-user"></i
                                          ></span>
                                          ${to_bool(scheduled_message.is_dm_with_self)
                                              ? html`
                                                    <span class="private_message_header_name"
                                                        >${$t({defaultMessage: "You"})}</span
                                                    >
                                                `
                                              : html`
                                                    <span class="private_message_header_name"
                                                        >${$t(
                                                            {
                                                                defaultMessage:
                                                                    "You and {recipients}",
                                                            },
                                                            {
                                                                recipients:
                                                                    scheduled_message.recipients,
                                                            },
                                                        )}</span
                                                    >
                                                `}
                                      </div>
                                      ${{
                                          __html: render_scheduled_message_stream_pm_common(
                                              scheduled_message,
                                          ),
                                      }}
                                  </div>
                              </div>
                          `}
                    <div
                        class="message_row${!to_bool(scheduled_message.is_stream)
                            ? " private-message"
                            : ""}"
                        role="listitem"
                    >
                        <div class="messagebox">
                            <div class="messagebox-content">
                                <div class="message_top_line">
                                    <div class="overlay_message_controls">
                                        ${{
                                            __html: render_icon_button({
                                                ["aria-label"]: $t({defaultMessage: "Delete"}),
                                                ["data-tooltip-template-id"]:
                                                    "delete-scheduled-message-tooltip-template",
                                                icon: "trash",
                                                custom_classes:
                                                    "delete-overlay-message tippy-zulip-delayed-tooltip",
                                                intent: "danger",
                                            }),
                                        }}
                                    </div>
                                </div>
                                <div
                                    class="message_content rendered_markdown restore-overlay-message"
                                >
                                    ${{
                                        __html: postprocess_content(
                                            scheduled_message.rendered_content,
                                        ),
                                    }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `,
    );
    return to_html(out);
}
