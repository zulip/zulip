import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_buddy_list_tooltip_content(context) {
    const out = html`<div class="buddy_list_tooltip_content">
        <div>
            ${context.first_line}
            ${to_bool(context.show_you)
                ? html` <span class="my_user_status">${$t({defaultMessage: "(you)"})}</span> `
                : ""}
        </div>
        ${to_bool(context.second_line)
            ? html`
                  <div
                      class="tooltip-inner-content ${to_bool(context.is_deactivated)
                          ? "italic"
                          : ""}"
                  >
                      ${context.second_line}
                  </div>
              `
            : ""}${to_bool(context.third_line)
            ? html`
                  <div
                      class="tooltip-inner-content ${to_bool(context.is_deactivated)
                          ? "italic"
                          : ""}"
                  >
                      ${context.third_line}
                  </div>
              `
            : ""}
    </div> `;
    return to_html(out);
}
