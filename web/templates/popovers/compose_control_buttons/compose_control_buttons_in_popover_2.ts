import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import {$t} from "../../../src/i18n.ts";

export default function render_compose_control_buttons_in_popover_2(context) {
    const out = html`<div
        class="compose-control-buttons-container preview_mode_disabled ${to_bool(
            context.inside_popover,
        )
            ? " show_in_popover "
            : ""}"
    >
        <a
            role="button"
            data-format-type="link"
            class="compose_control_button zulip-icon zulip-icon-link formatting_button"
            aria-label="${$t({defaultMessage: "Link"})}"
            ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
            data-tooltip-template-id="link-tooltip"
            data-tippy-maxWidth="none"
        ></a>
        <a
            role="button"
            data-format-type="bold"
            class="compose_control_button zulip-icon zulip-icon-bold formatting_button"
            aria-label="${$t({defaultMessage: "Bold"})}"
            ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
            data-tooltip-template-id="bold-tooltip"
            data-tippy-maxWidth="none"
        ></a>
        <a
            role="button"
            data-format-type="italic"
            class="compose_control_button zulip-icon zulip-icon-italic formatting_button"
            aria-label="${$t({defaultMessage: "Italic"})}"
            ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
            data-tooltip-template-id="italic-tooltip"
            data-tippy-maxWidth="none"
        ></a>
        <a
            role="button"
            data-format-type="strikethrough"
            class="compose_control_button zulip-icon zulip-icon-strikethrough formatting_button"
            aria-label="${$t({defaultMessage: "Strikethrough"})}"
            ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
            data-tippy-content="${$t({defaultMessage: "Strikethrough"})}"
        ></a>
        ${to_bool(context.inside_popover) ? html` <div class="divider">|</div> ` : ""}
    </div> `;
    return to_html(out);
}
