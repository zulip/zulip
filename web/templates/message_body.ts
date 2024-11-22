import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_edited_notice from "./edited_notice.ts";
import render_message_avatar from "./message_avatar.ts";
import render_message_controls from "./message_controls.ts";
import render_message_controls_failed_msg from "./message_controls_failed_msg.ts";
import render_message_hidden_dialog from "./message_hidden_dialog.ts";
import render_message_reactions from "./message_reactions.ts";
import render_status_emoji from "./status_emoji.ts";
import render_user_full_name from "./user_full_name.ts";

export default function render_message_body(context) {
    const out = html`${to_bool(context.include_sender)
            ? html` ${{__html: render_message_avatar(context)}}`
            : ""}<span class="message_sender">
            ${to_bool(context.include_sender)
                ? html` <span class="sender_info_hover sender_name" role="button" tabindex="0">
                          <span
                              class="view_user_card_tooltip sender_name_text"
                              data-is-bot="${context.sender_is_bot}"
                          >
                              ${{
                                  __html: render_user_full_name({
                                      should_add_guest_user_indicator:
                                          context.should_add_guest_indicator_for_sender,
                                      name: context.msg.sender_full_name,
                                  }),
                              }}
                          </span>
                          ${!to_bool(context.status_message)
                              ? html` ${{
                                    __html: render_status_emoji(context.msg.status_emoji_info),
                                }}`
                              : ""}
                      </span>
                      ${to_bool(context.sender_is_bot)
                          ? html`
                                <i
                                    class="zulip-icon zulip-icon-bot"
                                    aria-label="${$t({defaultMessage: "Bot"})}"
                                ></i>
                            `
                          : ""}${to_bool(context.status_message)
                          ? html` <span class="rendered_markdown status-message"
                                    >${{__html: postprocess_content(context.status_message)}}</span
                                >
                                ${to_bool(context.message_edit_notices_for_status_message)
                                    ? html` ${{__html: render_edited_notice(context)}}`
                                    : ""}`
                          : ""}${to_bool(context.message_edit_notices_alongside_sender)
                          ? html` ${{__html: render_edited_notice(context)}}`
                          : ""}`
                : ""}</span
        >

        <a
            ${!to_bool(context.msg.locally_echoed) ? html`href="${context.msg.url}"` : ""}
            class="message-time"
        >
            ${!to_bool(context.include_sender)
                ? html` <span class="copy-paste-text">&nbsp;</span> `
                : ""}
            ${context.timestr}
        </a>

        ${!to_bool(context.msg.failed_request) && to_bool(context.msg.locally_echoed)
            ? html`
                  <span
                      data-tooltip-template-id="slow-send-spinner-tooltip-template"
                      class="fa fa-circle-o-notch slow-send-spinner${!to_bool(
                          context.msg.show_slow_send_spinner,
                      )
                          ? " hidden"
                          : ""}"
                  ></span>
              `
            : ""}
        <div class="message_controls no-select">
            ${to_bool(context.msg.locally_echoed)
                ? to_bool(context.msg.failed_request)
                    ? html` ${{__html: render_message_controls_failed_msg()}}`
                    : ""
                : html` ${{__html: render_message_controls(context)}}`}
        </div>

        ${!to_bool(context.status_message)
            ? !to_bool(context.is_hidden)
                ? html`
                      <div class="message_content rendered_markdown">
                          ${to_bool(context.use_match_properties)
                              ? html` ${{__html: postprocess_content(context.msg.match_content)}} `
                              : html` ${{__html: postprocess_content(context.msg.content)}} `}
                      </div>
                  `
                : html`
                      <div class="message_content rendered_markdown">
                          ${{__html: render_message_hidden_dialog()}}
                      </div>
                  `
            : ""}
        ${to_bool(context.message_edit_notices_in_left_col)
            ? {__html: render_edited_notice(context)}
            : ""}
        <div class="message_length_controller"></div>

        ${!to_bool(context.is_hidden) && to_bool(context.msg.message_reactions)
            ? html` ${{__html: render_message_reactions(context)}}`
            : ""}`;
    return to_html(out);
}
