import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_compose_control_buttons_in_popover(context) {
    const out = html`<div class="compose-control-buttons-container preview_mode_disabled">
            <a
                role="button"
                data-format-type="numbered"
                class="compose_control_button zulip-icon zulip-icon-ordered-list formatting_button"
                aria-label="${$t({defaultMessage: "Numbered list"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Numbered list"})}"
            ></a>
            <a
                role="button"
                data-format-type="bulleted"
                class="compose_control_button zulip-icon zulip-icon-unordered-list formatting_button"
                aria-label="${$t({defaultMessage: "Bulleted list"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Bulleted list"})}"
            ></a>
            <div class="divider">|</div>
            <a
                role="button"
                data-format-type="quote"
                class="compose_control_button zulip-icon zulip-icon-quote formatting_button"
                aria-label="${$t({defaultMessage: "Quote"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Quote"})}"
            ></a>
            <a
                role="button"
                data-format-type="spoiler"
                class="compose_control_button zulip-icon zulip-icon-spoiler formatting_button"
                aria-label="${$t({defaultMessage: "Spoiler"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Spoiler"})}"
            ></a>
            <a
                role="button"
                data-format-type="code"
                class="compose_control_button zulip-icon zulip-icon-code formatting_button"
                aria-label="${$t({defaultMessage: "Code"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Code"})}"
            ></a>
            <a
                role="button"
                data-format-type="latex"
                class="compose_control_button zulip-icon zulip-icon-math formatting_button"
                aria-label="${$t({defaultMessage: "Math (LaTeX)"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Math (LaTeX)"})}"
            ></a>
            <div class="divider">|</div>
        </div>
        <a
            role="button"
            class="compose_control_button compose_help_button zulip-icon zulip-icon-question"
            tabindex="0"
            data-tippy-content="${$t({defaultMessage: "Message formatting"})}"
            data-overlay-trigger="message-formatting"
        ></a> `;
    return to_html(out);
}
