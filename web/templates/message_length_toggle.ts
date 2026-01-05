import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_message_length_toggle(context) {
    const out =
        context.toggle_type === "expander"
            ? html`<button
                  type="button"
                  class="message_expander message_length_toggle"
                  ${to_bool(context.tooltip_template_id)
                      ? html`
                            data-enable-tooltip="true"
                            data-tooltip-template-id="${context.tooltip_template_id}"
                        `
                      : html` data-enable-tooltip="false" `}
              >
                  ${context.label_text}
              </button> `
            : context.toggle_type === "condenser"
              ? html`<button
                    type="button"
                    class="message_condenser message_length_toggle"
                    ${to_bool(context.tooltip_template_id)
                        ? html`
                              data-enable-tooltip="true"
                              data-tooltip-template-id="${context.tooltip_template_id}"
                          `
                        : html` data-enable-tooltip="false" `}
                >
                    ${context.label_text}
                </button> `
              : "";
    return to_html(out);
}
