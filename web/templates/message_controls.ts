import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_controls(context) {
    const out = html`${!to_bool(context.is_archived)
            ? html`${to_bool(context.msg.sent_by_me)
                  ? html` <div class="edit_content message_control_button"></div> `
                  : ""}
              ${!to_bool(context.msg.sent_by_me)
                  ? html`
                        <div
                            class="reaction_button message_control_button"
                            data-tooltip-template-id="add-emoji-tooltip-template"
                        >
                            <div class="emoji-message-control-button-container">
                                <i
                                    class="message-controls-icon zulip-icon zulip-icon-smile"
                                    aria-label="${$t({defaultMessage: "Add emoji reaction"})} (:)"
                                    role="button"
                                    aria-haspopup="true"
                                    tabindex="0"
                                ></i>
                            </div>
                        </div>
                    `
                  : ""}`
            : ""}
        <div
            class="actions_hover message_control_button"
            data-tooltip-template-id="message-actions-tooltip-template"
        >
            <i
                class="message-controls-icon message-actions-menu-button zulip-icon zulip-icon-more-vertical-spread"
                role="button"
                aria-haspopup="true"
                tabindex="0"
                aria-label="${$t({defaultMessage: "Message actions"})}"
            ></i>
        </div>

        <div
            class="star_container message_control_button ${to_bool(context.msg.starred)
                ? ""
                : "empty-star"}"
            data-tooltip-template-id="${to_bool(context.msg.starred)
                ? "unstar"
                : "star"}-message-tooltip-template"
        >
            <i
                role="button"
                tabindex="0"
                class="message-controls-icon star zulip-icon ${to_bool(context.msg.starred)
                    ? "zulip-icon-star-filled"
                    : "zulip-icon-star"}"
            ></i>
        </div> `;
    return to_html(out);
}
