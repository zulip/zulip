import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_dropdown_widget_wrapper from "./dropdown_widget_wrapper.ts";

export default function render_move_topic_to_stream(context) {
    const out = html`${!(
            to_bool(context.from_message_actions_popover) || to_bool(context.only_topic_edit)
        )
            ? html`<p class="white-space-preserve-wrap">
                  ${$html_t(
                      {defaultMessage: "Move all messages in <strong>{topic_name}</strong>"},
                      {topic_name: context.topic_name},
                  )}
                  to:
              </p> `
            : ""}
        <form id="move_topic_form">
            ${to_bool(context.only_topic_edit)
                ? html` <p>${$t({defaultMessage: "Rename topic to:"})}</p> `
                : to_bool(context.from_message_actions_popover)
                  ? html` <p>${$t({defaultMessage: "Move messages to:"})}</p> `
                  : ""}
            <div class="topic_stream_edit_header">
                ${!to_bool(context.only_topic_edit)
                    ? html`
                          ${{
                              __html: render_dropdown_widget_wrapper({
                                  widget_name: "move_topic_to_stream",
                              }),
                          }} <i class="fa fa-angle-right" aria-hidden="true"></i>
                      `
                    : ""}
                <input
                    name="new_topic_name"
                    type="text"
                    class="move_messages_edit_topic modal_text_input"
                    autocomplete="off"
                    value="${context.topic_name}"
                    ${to_bool(context.disable_topic_input) ? "disabled" : ""}
                />
                <input name="old_topic_name" type="hidden" value="${context.topic_name}" />
                <input
                    name="current_stream_id"
                    type="hidden"
                    value="${context.current_stream_id}"
                />
                ${to_bool(context.from_message_actions_popover)
                    ? html`
                          <select
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
                      `
                    : ""}
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
