import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_icon_button from "./components/icon_button.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_draft(context) {
    const out = html`<div
        class="draft-message-row overlay-message-row"
        data-draft-id="${context.draft_id}"
    >
        <div class="draft-message-info-box overlay-message-info-box" tabindex="0">
            ${to_bool(context.is_stream)
                ? html`
                      <div
                          class="message_header message_header_stream restore-overlay-message overlay-message-header"
                      >
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
                                      : html`
                                            <span class="drafts-unknown-msg-header-field"
                                                >${$t({
                                                    defaultMessage: "No channel selected",
                                                })}</span
                                            >
                                        `}
                              </div>
                              <span class="stream_topic_separator"
                                  ><i class="zulip-icon zulip-icon-chevron-right"></i
                              ></span>
                              <span class="stream_topic">
                                  <span class="message_label_clickable narrows_by_topic">
                                      <span
                                          class="stream-topic-inner ${to_bool(
                                              context.is_empty_string_topic,
                                          )
                                              ? "empty-topic-display"
                                              : ""}"
                                          >${context.topic_display_name}</span
                                      >
                                  </span>
                              </span>
                              <span class="recipient_bar_controls"></span>
                              <div class="recipient_row_date">${context.time_stamp}</div>
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
                                  ${to_bool(context.is_dm_with_self)
                                      ? html`
                                            <span class="private_message_header_name"
                                                >${$t({defaultMessage: "You"})}</span
                                            >
                                        `
                                      : to_bool(context.has_recipient_data)
                                        ? html`
                                              <span class="private_message_header_name"
                                                  >${$t(
                                                      {defaultMessage: "You and {recipients}"},
                                                      {recipients: context.recipients},
                                                  )}</span
                                              >
                                          `
                                        : html`
                                              <span class="drafts-unknown-msg-header-field"
                                                  >${$t({defaultMessage: "No DM recipients"})}</span
                                              >
                                          `}
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
                                <span
                                    class="copy-button copy-overlay-message tippy-zulip-delayed-tooltip"
                                    data-draft-id="${context.draft_id}"
                                    data-tippy-content="${$t({defaultMessage: "Copy draft"})}"
                                    aria-label="${$t({defaultMessage: "Copy draft"})}"
                                    role="button"
                                >
                                    <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                                </span>
                                ${{
                                    __html: render_icon_button({
                                        ["aria-label"]: $t({defaultMessage: "Delete"}),
                                        ["data-tooltip-template-id"]:
                                            "delete-draft-tooltip-template",
                                        icon: "trash",
                                        custom_classes:
                                            "delete-overlay-message tippy-zulip-delayed-tooltip",
                                        intent: "danger",
                                    }),
                                }}
                                <div class="draft-selection-tooltip">
                                    <i
                                        class="fa fa-square-o fa-lg draft-selection-checkbox"
                                        aria-hidden="true"
                                    ></i>
                                </div>
                            </div>
                        </div>
                        <div class="message_content rendered_markdown restore-overlay-message">
                            ${{__html: postprocess_content(context.content)}}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
