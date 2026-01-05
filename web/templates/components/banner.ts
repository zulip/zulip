import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import render_action_button from "./action_button.ts";
import render_icon_button from "./icon_button.ts";

export default function render_banner(context, content) {
    const out = html`<div
        ${to_bool(context.process) ? html`data-process="${context.process}"` : ""}
        class="${to_bool(context.custom_classes)
            ? html`${context.custom_classes} `
            : ""}banner banner-${context.intent}"
    >
        <span class="banner-content">
            <span class="banner-label">
                ${to_bool(context.label) ? html` ${context.label} ` : html` ${content(context)}`}
            </span>
            ${to_bool(context.buttons)
                ? html`
                      <span class="banner-action-buttons">
                          ${to_array(context.buttons).map((button) =>
                              to_bool(button.intent)
                                  ? html` ${{__html: render_action_button(button)}}`
                                  : html` ${{
                                        __html: render_action_button({
                                            intent: context.intent,
                                            ...button,
                                        }),
                                    }}`,
                          )}</span
                      >
                  `
                : ""}
        </span>
        ${to_bool(context.close_button)
            ? html` ${{
                  __html: render_icon_button({
                      intent: context.intent,
                      icon: "close",
                      custom_classes: "banner-close-action banner-close-button",
                  }),
              }}`
            : ""}
    </div> `;
    return to_html(out);
}
