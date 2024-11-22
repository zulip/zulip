import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";

export default function render_message_edit_history(context) {
    const out = /* Client-side Handlebars template for viewing message edit history. */ html`
        ${to_array(context.edited_messages).map(
            (message) => html`
                <div
                    class="message-edit-message-row overlay-message-row"
                    data-message-edit-history-id="${message.timestamp}"
                >
                    <div
                        class="message-edit-message-info-box overlay-message-info-box"
                        tabindex="0"
                    >
                        ${to_bool(message.is_stream)
                            ? html`
                                  <div class="message_header message_header_stream">
                                      <div
                                          class="message-header-contents"
                                          style="background: ${message.recipient_bar_color};"
                                      >
                                          <div class="message_label_clickable stream_label">
                                              <span class="private_message_header_name"
                                                  >${message.edited_by_notice}</span
                                              >
                                          </div>
                                          <div
                                              class="recipient_row_date"
                                              title="${$t({defaultMessage: "Last modified"})}"
                                          >
                                              ${$t(
                                                  {defaultMessage: "{edited_at_time}"},
                                                  {edited_at_time: message.edited_at_time},
                                              )}
                                          </div>
                                      </div>
                                  </div>
                              `
                            : html`
                                  <div class="message_header message_header_private_message">
                                      <div class="message-header-contents">
                                          <div class="message_label_clickable stream_label">
                                              <span class="private_message_header_name"
                                                  >${message.edited_by_notice}</span
                                              >
                                          </div>
                                          <div
                                              class="recipient_row_date"
                                              title="${$t({defaultMessage: "Last modified"})}"
                                          >
                                              ${$t(
                                                  {defaultMessage: "{edited_at_time}"},
                                                  {edited_at_time: message.edited_at_time},
                                              )}
                                          </div>
                                      </div>
                                  </div>
                              `}
                        <div
                            class="message_row${!to_bool(message.is_stream)
                                ? " private-message"
                                : ""}"
                            role="listitem"
                        >
                            <div class="messagebox">
                                <div class="messagebox-content">
                                    ${to_bool(message.topic_edited)
                                        ? html`
                                              <div
                                                  class="message_content message_edit_history_content"
                                              >
                                                  <p>
                                                      Topic:
                                                      <span class="highlight_text_inserted"
                                                          >${message.new_topic}</span
                                                      >
                                                      <span class="highlight_text_deleted"
                                                          >${message.prev_topic}</span
                                                      >
                                                  </p>
                                              </div>
                                          `
                                        : ""}${to_bool(message.stream_changed)
                                        ? html`
                                              <div
                                                  class="message_content message_edit_history_content"
                                              >
                                                  <p>
                                                      Stream:
                                                      <span class="highlight_text_inserted"
                                                          >${message.new_stream}</span
                                                      >
                                                      <span class="highlight_text_deleted"
                                                          >${message.prev_stream}</span
                                                      >
                                                  </p>
                                              </div>
                                          `
                                        : ""}${to_bool(message.body_to_render)
                                        ? html`
                                              <div
                                                  class="message_content rendered_markdown message_edit_history_content"
                                              >
                                                  ${{
                                                      __html: postprocess_content(
                                                          message.body_to_render,
                                                      ),
                                                  }}
                                              </div>
                                          `
                                        : ""}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `,
        )}
    `;
    return to_html(out);
}
