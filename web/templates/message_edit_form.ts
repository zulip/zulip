import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_compose_control_buttons from "./compose_control_buttons.ts";

export default function render_message_edit_form(context) {
    const out = /* Client-side Handlebars template for rendering the message edit form. */ html`<div
        class="message_edit"
    >
        <div class="message_edit_form">
            <form class="edit-form" id="edit_form_${context.message_id}">
                <div class="edit_form_banners"></div>
                <div
                    class="edit-controls edit-content-container ${to_bool(context.is_editable)
                        ? "surround-formatting-buttons-row"
                        : ""}"
                >
                    <div class="message-edit-textbox">
                        <span
                            class="copy_message copy-button copy-button-square tippy-zulip-tooltip"
                            data-tippy-content="${$t({defaultMessage: "Copy and close"})}"
                            aria-label="${$t({defaultMessage: "Copy and close"})}"
                            role="button"
                        >
                            <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                        </span>
                        <textarea class="message_edit_content message-textarea">
${context.content}</textarea
                        >
                    </div>
                    <div
                        class="scrolling_list preview_message_area"
                        id="preview_message_area_${context.message_id}"
                        style="display:none;"
                    >
                        <div class="markdown_preview_spinner"></div>
                        <div class="preview_content rendered_markdown"></div>
                    </div>
                </div>
                <div class="action-buttons">
                    <div class="controls edit-controls">
                        ${to_bool(context.is_editable)
                            ? html`
                                  <div
                                      class="message-edit-feature-group compose-scrolling-buttons-container"
                                  >
                                      ${{__html: render_compose_control_buttons(context)}}
                                      <button
                                          type="button"
                                          class="formatting-control-scroller-button formatting-scroller-forward"
                                      >
                                          <i
                                              class="scroller-forward-icon zulip-icon zulip-icon-compose-scroll-right"
                                          ></i>
                                      </button>
                                      <button
                                          type="button"
                                          class="formatting-control-scroller-button formatting-scroller-backward"
                                      >
                                          <i
                                              class="scroller-backward-icon zulip-icon zulip-icon-compose-scroll-left"
                                          ></i>
                                      </button>
                                  </div>
                              `
                            : ""}
                        <div class="message-edit-buttons-and-timer">
                            ${to_bool(context.is_editable)
                                ? html`
                                      <div class="message_edit_save_container">
                                          <button
                                              type="button"
                                              class="message-actions-button message_edit_save"
                                          >
                                              <img class="loader" alt="" src="" />
                                              <span>${$t({defaultMessage: "Save"})}</span>
                                          </button>
                                      </div>
                                      <button
                                          type="button"
                                          class="message-actions-button message_edit_cancel"
                                      >
                                          <span>${$t({defaultMessage: "Cancel"})}</span>
                                      </button>
                                      <span
                                          class="tippy-zulip-tooltip message-limit-indicator"
                                          data-tippy-content="${$t(
                                              {
                                                  defaultMessage:
                                                      "Maximum message length: {max_message_length} characters",
                                              },
                                              {max_message_length: context.max_message_length},
                                          )}"
                                      ></span>
                                      <div class="message-edit-timer">
                                          <span
                                              class="message_edit_countdown_timer
                                  tippy-zulip-tooltip"
                                              data-tippy-content="${$t(
                                                  {
                                                      defaultMessage:
                                                          "This organization is configured to restrict editing of message content to {minutes_to_edit} minutes after it is sent.",
                                                  },
                                                  {minutes_to_edit: context.minutes_to_edit},
                                              )}"
                                          ></span>
                                      </div>
                                  `
                                : html`
                                      <button
                                          type="button"
                                          class="message-actions-button message_edit_close"
                                      >
                                          <span>${$t({defaultMessage: "Close"})}</span>
                                      </button>
                                  `}
                        </div>
                    </div>
                </div>
            </form>
        </div>
    </div> `;
    return to_html(out);
}
