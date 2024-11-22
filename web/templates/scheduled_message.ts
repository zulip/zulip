import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
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
                              <div class="message_header message_header_stream">
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
                                          <div class="message_label_clickable narrows_by_topic">
                                              <span>${scheduled_message.topic}</span>
                                          </div>
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
                              <div class="message_header message_header_private_message">
                                  <div class="message-header-contents">
                                      <div class="message_label_clickable stream_label">
                                          <span class="private_message_header_icon"
                                              ><i class="zulip-icon zulip-icon-user"></i
                                          ></span>
                                          <span class="private_message_header_name"
                                              >${$t(
                                                  {defaultMessage: "You and {recipients}"},
                                                  {recipients: scheduled_message.recipients},
                                              )}</span
                                          >
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
                                        <i
                                            class="fa fa-pencil fa-lg restore-overlay-message tippy-zulip-tooltip"
                                            aria-hidden="true"
                                            data-tooltip-template-id="restore-scheduled-message-tooltip-template"
                                        ></i>
                                        <i
                                            class="fa fa-trash-o fa-lg delete-overlay-message tippy-zulip-tooltip"
                                            aria-hidden="true"
                                            data-tooltip-template-id="delete-scheduled-message-tooltip-template"
                                        ></i>
                                    </div>
                                </div>
                                <div
                                    class="message_content rendered_markdown restore-overlay-message tippy-zulip-delayed-tooltip"
                                    data-tooltip-template-id="restore-scheduled-message-tooltip-template"
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
