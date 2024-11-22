import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_status_emoji_selector from "./status_emoji_selector.ts";

export default function render_set_status_overlay(context) {
    const out = html`<div class="user-status-content-wrapper">
            <div
                class="tippy-zulip-tooltip"
                data-tippy-content="${$t({defaultMessage: "Select emoji"})}"
                data-tippy-placement="top"
                aria-label="${$t({defaultMessage: "Select emoji"})}"
                id="selected_emoji"
            >
                <div class="status-emoji-wrapper" tabindex="0">
                    ${{__html: render_status_emoji_selector(context)}}
                </div>
            </div>
            <input
                type="text"
                class="user-status modal_text_input"
                placeholder="${$t({defaultMessage: "Your status"})}"
                maxlength="60"
            />
            <button
                type="button"
                class="bootstrap-btn clear_search_button"
                id="clear_status_message_button"
                disabled="disabled"
            >
                <i class="fa fa-remove" aria-hidden="true"></i>
            </button>
        </div>
        <div class="user-status-options">
            ${to_array(context.default_status_messages_and_emoji_info).map(
                (status) => html`
                    <button type="button" class="button no-style user-status-value">
                        ${to_bool(status.emoji.emoji_alt_code)
                            ? html`
                                  <div class="emoji_alt_code">
                                      &nbsp;:${status.emoji.emoji_name}:
                                  </div>
                              `
                            : to_bool(status.emoji.url)
                              ? html` <img src="${status.emoji.url}" class="emoji status-emoji" /> `
                              : html`
                                    <div
                                        class="emoji status-emoji emoji-${status.emoji.emoji_code}"
                                    ></div>
                                `}
                        ${status.status_text}
                    </button>
                `,
            )}
        </div> `;
    return to_html(out);
}
