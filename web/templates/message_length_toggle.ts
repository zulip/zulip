import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_message_length_toggle(context) {
    const out =
        context.toggle_type === "expander"
            ? html`
                  <button
                      type="button"
                      class="message_expander message_length_toggle tippy-zulip-delayed-tooltip"
                      data-tooltip-template-id="message-expander-tooltip-template"
                  >
                      ${$t({defaultMessage: "Show more"})}
                  </button>
              `
            : context.toggle_type === "condenser"
              ? html`
                    <button
                        type="button"
                        class="message_condenser message_length_toggle tippy-zulip-delayed-tooltip"
                        data-tooltip-template-id="message-condenser-tooltip-template"
                    >
                        ${$t({defaultMessage: "Show less"})}
                    </button>
                `
              : "";
    return to_html(out);
}
