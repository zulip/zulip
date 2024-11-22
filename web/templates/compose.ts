import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_compose_control_buttons from "./compose_control_buttons.ts";
import render_dropdown_widget_wrapper from "./dropdown_widget_wrapper.ts";

export default function render_compose(context) {
    const out = html`<div id="compose-content">
        ${
            /* scroll to bottom button is not part of compose but
    helps us align it at various screens sizes with
    minimal css and no JS. We keep it `position: absolute` to prevent
    it changing compose box layout in any way. */ ""
        }
        <div id="scroll-to-bottom-button-container" aria-hidden="true">
            <div
                id="scroll-to-bottom-button-clickable-area"
                data-tooltip-template-id="scroll-to-bottom-button-tooltip-template"
            >
                <div id="scroll-to-bottom-button">
                    <i class="scroll-to-bottom-icon fa fa-chevron-down"></i>
                </div>
            </div>
        </div>
        <div id="compose_controls">
            <div id="compose_buttons">
                <div class="reply_button_container">
                    <div
                        class="compose-reply-button-wrapper"
                        data-reply-button-type="selected_message"
                    >
                        <button
                            type="button"
                            class="compose_reply_button"
                            id="left_bar_compose_reply_button_big"
                        >
                            ${$t({defaultMessage: "Compose message"})}
                        </button>
                    </div>
                    <button
                        type="button"
                        class="compose_new_conversation_button"
                        id="new_conversation_button"
                        data-tooltip-template-id="new_stream_message_button_tooltip_template"
                    >
                        ${$t({defaultMessage: "Start new conversation"})}
                    </button>
                </div>
                <span class="mobile_button_container">
                    <button
                        type="button"
                        class="compose_mobile_button"
                        id="left_bar_compose_mobile_button_big"
                        data-tooltip-template-id="left_bar_compose_mobile_button_tooltip_template"
                    >
                        +
                    </button>
                </span>
                ${!to_bool(context.embedded)
                    ? html`
                          <span class="new_direct_message_button_container">
                              <button
                                  type="button"
                                  class="compose_new_direct_message_button"
                                  id="new_direct_message_button"
                                  data-tooltip-template-id="new_direct_message_button_tooltip_template"
                              >
                                  ${$t({defaultMessage: "New direct message"})}
                              </button>
                          </span>
                      `
                    : ""}
            </div>
        </div>
        <div class="message_comp">
            <div id="compose_banners" data-simplebar data-simplebar-tab-index="-1"></div>
            <div class="composition-area">
                <form id="send_message_form" action="/json/messages" method="post">
                    <div class="compose_table">
                        <div id="compose_top">
                            <div id="compose-recipient">
                                ${{
                                    __html: render_dropdown_widget_wrapper({
                                        widget_name: "compose_select_recipient",
                                    }),
                                }}
                                <div class="topic-marker-container">
                                    <a
                                        role="button"
                                        class="conversation-arrow zulip-icon zulip-icon-chevron-right"
                                    ></a>
                                </div>
                                <div id="compose_recipient_box">
                                    <input
                                        type="text"
                                        name="stream_message_recipient_topic"
                                        id="stream_message_recipient_topic"
                                        maxlength="${context.max_topic_length}"
                                        value=""
                                        placeholder="${$t({defaultMessage: "Topic"})}"
                                        autocomplete="off"
                                        tabindex="0"
                                        aria-label="${$t({defaultMessage: "Topic"})}"
                                    />
                                    <button
                                        type="button"
                                        id="recipient_box_clear_topic_button"
                                        class="tippy-zulip-delayed-tooltip"
                                        data-tippy-content="${$t({defaultMessage: "Clear topic"})}"
                                        tabindex="-1"
                                    >
                                        <i class="zulip-icon zulip-icon-close"></i>
                                    </button>
                                </div>
                                <div
                                    id="compose-direct-recipient"
                                    data-before="${$t({defaultMessage: "You and"})}"
                                >
                                    <div class="pill-container">
                                        <div
                                            class="input"
                                            contenteditable="true"
                                            id="private_message_recipient"
                                            data-no-recipients-text="${$t({
                                                defaultMessage: "Add one or more users",
                                            })}"
                                            data-some-recipients-text="${$t({
                                                defaultMessage: "Add another user...",
                                            })}"
                                        ></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="messagebox">
                            <div
                                id="message-content-container"
                                class="surround-formatting-buttons-row"
                            >
                                <textarea
                                    class="new_message_textarea"
                                    name="content"
                                    id="compose-textarea"
                                    placeholder="${$t({
                                        defaultMessage: "Compose your message here",
                                    })}"
                                    tabindex="0"
                                    aria-label="${$t({
                                        defaultMessage: "Compose your message here...",
                                    })}"
                                ></textarea>
                                <div id="preview-message-area-container">
                                    <div
                                        class="scrolling_list preview_message_area"
                                        data-simplebar
                                        data-simplebar-tab-index="-1"
                                        id="preview_message_area"
                                        style="display:none;"
                                    >
                                        <div class="markdown_preview_spinner"></div>
                                        <div class="preview_content rendered_markdown"></div>
                                    </div>
                                </div>
                                <div class="composebox-buttons">
                                    <button
                                        type="button"
                                        class="maximize-composebox-button zulip-icon zulip-icon-maximize-diagonal"
                                        aria-label="${$t({defaultMessage: "Maximize compose box"})}"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Maximize compose box",
                                        })}"
                                    ></button>
                                    <button
                                        type="button"
                                        class="expand-composebox-button zulip-icon zulip-icon-expand-diagonal"
                                        aria-label="${$t({defaultMessage: "Expand compose box"})}"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Expand compose box",
                                        })}"
                                    ></button>
                                    <button
                                        type="button"
                                        class="collapse-composebox-button zulip-icon zulip-icon-collapse-diagonal"
                                        aria-label="${$t({defaultMessage: "Collapse compose box"})}"
                                        data-tippy-content="${$t({
                                            defaultMessage: "Collapse compose box",
                                        })}"
                                    ></button>
                                </div>
                                <div class="drag"></div>
                            </div>

                            <div id="message-send-controls-container">
                                <a
                                    id="compose-drafts-button"
                                    role="button"
                                    class="send-control-button hide-sm"
                                    tabindex="0"
                                    href="#drafts"
                                >
                                    <span class="compose-drafts-text"
                                        >${$t({defaultMessage: "Drafts"})}</span
                                    ><span class="compose-drafts-count-container"
                                        >(<span class="compose-drafts-count"></span>)</span
                                    >
                                </a>
                                <span id="compose-limit-indicator"></span>
                                <div class="message-send-controls">
                                    <button
                                        type="submit"
                                        id="compose-send-button"
                                        class="send_message compose-submit-button compose-send-or-save-button"
                                        aria-label="${$t({defaultMessage: "Send"})}"
                                    >
                                        <img class="loader" alt="" src="" />
                                        <i class="zulip-icon zulip-icon-send"></i>
                                    </button>
                                    <button
                                        class="send-control-button send-related-action-button"
                                        id="send_later"
                                        tabindex="0"
                                        type="button"
                                        data-tippy-content="${$t({defaultMessage: "Send options"})}"
                                    >
                                        <i class="zulip-icon zulip-icon-more-vertical"></i>
                                    </button>
                                </div>
                            </div>

                            <div id="message-formatting-controls-container">
                                ${{__html: render_compose_control_buttons(context)}}
                            </div>
                        </div>
                    </div>
                </form>
            </div>
            <button
                type="button"
                class="close zulip-icon zulip-icon-close"
                id="compose_close"
                data-tooltip-template-id="compose_close_tooltip_template"
            ></button>
        </div>
    </div> `;
    return to_html(out);
}
