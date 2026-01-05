import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_icon_button from "./icon_button.ts";

export default function render_input_wrapper(context, content) {
    const out = /* This is used to wrap any input element that needs to be styled as a Zulip input.
Usage example:
{{#> components/input_wrapper . input_type="filter-input" custom_classes="inbox-search-wrapper" icon="search" input_button_icon="close"}}
<input type="text" id="{{INBOX_SEARCH_ID}}" class="input-element" value="{{search_val}}" autocomplete="off" placeholder="{{t 'Filter' }}" />
{{/components/input_wrapper}} */ html`
        <div
            ${to_bool(context.id) ? html`id="${context.id}"` : ""}
            class="input-element-wrapper${to_bool(context.input_type)
                ? html` ${context.input_type}`
                : ""}${to_bool(context.custom_classes)
                ? html` ${context.custom_classes}`
                : ""}${to_bool(context.icon) ? " has-input-icon" : ""}${to_bool(
                context.input_button_icon,
            )
                ? " has-input-button"
                : ""}"
        >
            ${to_bool(context.icon)
                ? html`
                      <i
                          class="input-icon zulip-icon zulip-icon-${context.icon}"
                          aria-hidden="true"
                      ></i>
                  `
                : ""}
            ${content(context)}${to_bool(context.input_button_icon)
                ? context.input_type === "filter-input"
                    ? html` ${{
                          __html: render_icon_button({
                              intent: "neutral",
                              icon: context.input_button_icon,
                              squared: true,
                              custom_classes: "input-button input-close-filter-button",
                          }),
                      }}`
                    : html` ${{
                          __html: render_icon_button({
                              intent: "neutral",
                              icon: context.input_button_icon,
                              squared: true,
                              custom_classes: "input-button",
                          }),
                      }}`
                : ""}
        </div>
    `;
    return to_html(out);
}
