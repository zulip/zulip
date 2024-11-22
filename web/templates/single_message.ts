import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import render_message_body from "./message_body.ts";

export default function render_single_message(context) {
    const out = html`<div
        id="message-row-${context.message_list_id}-${context.msg.id}"
        data-message-id="${context.msg.id}"
        class="message_row${!to_bool(context.msg.is_stream) ? " private-message" : ""}${to_bool(
            context.include_sender,
        )
            ? " messagebox-includes-sender"
            : ""}${to_bool(context.mention_classname)
            ? html` ${context.mention_classname}`
            : ""}${to_bool(context.msg.unread) ? " unread" : ""} ${to_bool(
            context.msg.locally_echoed,
        )
            ? "locally-echoed"
            : ""} selectable_row"
        role="listitem"
    >
        ${to_bool(context.want_date_divider)
            ? html`
                  <div class="unread_marker date_unread_marker">
                      <div class="unread-marker-fill"></div>
                  </div>
                  <div class="date_row no-select">${{__html: context.date_divider_html}}</div>
              `
            : ""}
        <div class="unread_marker message_unread_marker">
            <div class="unread-marker-fill"></div>
        </div>
        <div class="messagebox">
            <div
                class="messagebox-content ${to_bool(context.status_message) ? "is-me-message" : ""}"
            >
                ${{__html: render_message_body(context)}}${
                    /* message_edit_form.hbs is inserted here when editing a message. */ ""
                }
            </div>
        </div>
    </div> `;
    return to_html(out);
}
