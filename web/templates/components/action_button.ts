import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_action_button(context) {
    const out = html`<button
        type="${to_bool(context.type) ? context.type : "button"}"
        ${to_bool(context.id) ? html`id="${context.id}"` : ""}
        class="${to_bool(context.custom_classes)
            ? html`${context.custom_classes} `
            : ""}action-button action-button-${context.attention}-${context.intent} ${to_bool(
            context.hidden,
        )
            ? "hide"
            : ""}"
        ${to_bool(context["data-tippy-content"])
            ? html`data-tippy-content="${context["data-tippy-content"]}"`
            : ""}
        ${to_bool(context["data-tooltip-template-id"])
            ? html`data-tooltip-template-id="${context["data-tooltip-template-id"]}"`
            : ""}
        tabindex="0"
        ${to_bool(context["aria-label"]) ? html`aria-label="${context["aria-label"]}"` : ""}
        ${to_bool(context.disabled) ? "disabled" : ""}
    >
        ${to_bool(context.icon)
            ? html` <i class="zulip-icon zulip-icon-${context.icon}" aria-hidden="true"></i> `
            : ""}${to_bool(context.label)
            ? html` <span class="action-button-label">${context.label}</span> `
            : ""}
    </button> `;
    return to_html(out);
}
