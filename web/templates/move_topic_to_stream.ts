import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_dropdown_widget_wrapper from "./dropdown_widget_wrapper.ts";
import render_topic_not_mandatory_placeholder_text from "./topic_not_mandatory_placeholder_text.ts";

export default function render_move_topic_to_stream(context) {
    const out = html`<form id="move_topic_form">
        <div class="move_topic_warning_container"></div>
        <div class="topic_stream_edit_header">
            ${!to_bool(context.only_topic_edit)
                ? html`
                      <div class="input-group">
                          <label class="modal-field-label"
                              >${$t({defaultMessage: "New channel"})}</label
                          >
                          ${{
                              __html: render_dropdown_widget_wrapper({
                                  widget_name: "move_topic_to_stream",
                              }),
                          }}
                      </div>
                  `
                : ""}
            <div class="input-group">
                <label for="move-topic-new-topic-name" class="modal-field-label"
                    >${$t({defaultMessage: "New topic"})}</label
                >
                <div id="move-topic-new-topic-input-wrapper">
                    <input
                        id="move-topic-new-topic-name"
                        name="new_topic_name"
                        type="text"
                        class="move_messages_edit_topic modal_text_input"
                        autocomplete="off"
                        value="${context.topic_name}"
                        ${to_bool(context.disable_topic_input) ? "disabled" : ""}
                        maxlength="${context.max_topic_length}"
                    />
                    <span class="move-topic-new-topic-placeholder placeholder">
                        ${{
                            __html: render_topic_not_mandatory_placeholder_text({
                                empty_string_topic_display_name:
                                    context.empty_string_topic_display_name,
                            }),
                        }}
                    </span>
                    <button
                        type="button"
                        id="clear_move_topic_new_topic_name"
                        class="clear_search_button"
                    >
                        <i class="zulip-icon zulip-icon-close"></i>
                    </button>
                </div>
                <div class="new-topic-name-error"></div>
            </div>
            <input name="old_topic_name" type="hidden" value="${context.topic_name}" />
            <input name="current_stream_id" type="hidden" value="${context.current_stream_id}" />
            ${to_bool(context.from_message_actions_popover)
                ? html`
                      <div class="input-group">
                          <label for="message_move_select_options"
                              >${$t({defaultMessage: "Which messages should be moved?"})}</label
                          >
                          <select
                              name="propagate_mode"
                              id="message_move_select_options"
                              class="message_edit_topic_propagate modal_select bootstrap-focus-style"
                          >
                              <option
                                  value="change_one"
                                  ${context.message_placement === "last" ? "selected" : ""}
                              >
                                  ${$t({defaultMessage: "Move only this message"})}
                              </option>
                              <option
                                  value="change_later"
                                  ${context.message_placement === "intermediate" ? "selected" : ""}
                              >
                                  ${$t({
                                      defaultMessage:
                                          "Move this and all following messages in this topic",
                                  })}
                              </option>
                              <option
                                  value="change_all"
                                  ${context.message_placement === "first" ? "selected" : ""}
                              >
                                  ${$t({defaultMessage: "Move all messages in this topic"})}
                              </option>
                          </select>
                      </div>
                  `
                : ""}
            <p id="move_messages_count"></p>
            <div class="topic_move_breadcrumb_messages">
                <label class="checkbox">
                    <input
                        class="send_notification_to_new_thread"
                        name="send_notification_to_new_thread"
                        type="checkbox"
                        ${to_bool(context.notify_new_thread) ? html`checked="checked"` : ""}
                    />
                    <span class="rendered-checkbox"></span>
                    ${$t({defaultMessage: "Send automated notice to new topic"})}
                </label>
                <label class="checkbox">
                    <input
                        class="send_notification_to_old_thread"
                        name="send_notification_to_old_thread"
                        type="checkbox"
                        ${to_bool(context.notify_old_thread) ? html`checked="checked"` : ""}
                    />
                    <span class="rendered-checkbox"></span>
                    ${$t({defaultMessage: "Send automated notice to old topic"})}
                </label>
            </div>
        </div>
    </form> `;
    return to_html(out);
}
