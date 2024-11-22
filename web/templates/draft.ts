import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_draft(context) {
    const out = html`<div
        class="draft-message-row overlay-message-row"
        data-draft-id="${context.draft_id}"
    >
        <div class="draft-message-info-box overlay-message-info-box" tabindex="0">
            ${to_bool(context.is_stream)
                ? html`
                      <div class="message_header message_header_stream">
                          <div
                              class="message-header-contents"
                              style="background: ${context.recipient_bar_color};"
                          >
                              <div class="message_label_clickable stream_label">
                                  <span
                                      class="stream-privacy-modified-color-${context.stream_id} stream-privacy filter-icon"
                                      style="color: ${context.stream_privacy_icon_color}"
                                  >
                                      ${{__html: render_stream_privacy(context)}}
                                  </span>
                                  ${to_bool(context.stream_name)
                                      ? html` ${context.stream_name} `
                                      : html` &nbsp; `}
                              </div>
                              <span class="stream_topic_separator"
                                  ><i class="zulip-icon zulip-icon-chevron-right"></i
                              ></span>
                              <span class="stream_topic">
                                  <div class="message_label_clickable narrows_by_topic">
                                      <span class="stream-topic-inner">${context.topic}</span>
                                  </div>
                              </span>
                              <span class="recipient_bar_controls"></span>
                              <div class="recipient_row_date">${context.time_stamp}</div>
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
                                          {recipients: context.recipients},
                                      )}</span
                                  >
                              </div>
                              <div class="recipient_row_date">${context.time_stamp}</div>
                          </div>
                      </div>
                  `}
            <div
                class="message_row${!to_bool(context.is_stream) ? " private-message" : ""}"
                role="listitem"
            >
                <div class="messagebox">
                    <div class="messagebox-content">
                        <div class="message_top_line">
                            <div class="overlay_message_controls">
                                <i
                                    class="fa fa-pencil fa-lg restore-overlay-message tippy-zulip-tooltip"
                                    aria-hidden="true"
                                    data-tooltip-template-id="restore-draft-tooltip-template"
                                ></i>
                                <i
                                    class="fa fa-trash-o fa-lg delete-overlay-message tippy-zulip-delayed-tooltip"
                                    aria-hidden="true"
                                    data-tooltip-template-id="delete-draft-tooltip-template"
                                ></i>
                                <div class="draft-selection-tooltip">
                                    <i
                                        class="fa fa-square-o fa-lg draft-selection-checkbox"
                                        aria-hidden="true"
                                    ></i>
                                </div>
                            </div>
                        </div>
                        <div
                            class="message_content rendered_markdown restore-overlay-message tippy-zulip-delayed-tooltip"
                            data-tooltip-template-id="restore-draft-tooltip-template"
                        >
                            ${{__html: postprocess_content(context.content)}}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
