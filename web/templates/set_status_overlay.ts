import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";
import render_status_emoji_selector from "./status_emoji_selector.ts";

export default function render_set_status_overlay(context) {
    const out = html`<div class="user-status-content-wrapper">
            <div
                class="user-status-emoji-picker"
                data-tippy-content="${$t({defaultMessage: "Select emoji"})}"
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
                id="user-status-input"
                placeholder="${$t({defaultMessage: "Your status"})}"
                maxlength="60"
            />
            ${{
                __html: render_icon_button({
                    icon: "close",
                    intent: "neutral",
                    squared: true,
                    id: "clear_status_message_button",
                }),
            }}
        </div>
        <ul class="user-status-options modal-options-list">
            ${to_array(context.default_status_messages_and_emoji_info).map(
                (status) => html`
                    <li class="user-status-option">
                        <a
                            class="modal-option-content trigger-click-on-enter user-status-value"
                            tabindex="0"
                        >
                            ${to_bool(status.emoji.emoji_alt_code)
                                ? html`
                                      <div class="emoji_alt_code">
                                          &nbsp;:${status.emoji.emoji_name}:
                                      </div>
                                  `
                                : to_bool(status.emoji.url)
                                  ? html`
                                        <img src="${status.emoji.url}" class="emoji status-emoji" />
                                    `
                                  : html`
                                        <div
                                            class="emoji status-emoji emoji-${status.emoji
                                                .emoji_code}"
                                        ></div>
                                    `} <span class="status-text">${status.status_text}</span>
                        </a>
                    </li>
                `,
            )}
        </ul> `;
    return to_html(out);
}
