import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_code_buttons_container(context) {
    const out = html`<div class="code-buttons-container">
        <span
            class="copy_codeblock copy-button copy-button-square"
            data-tippy-content="${$t({defaultMessage: "Copy code"})}"
            aria-label="${$t({defaultMessage: "Copy code"})}"
            role="button"
        >
            <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i> </span
        >${to_bool(context.show_playground_button)
            ? /* Display the "view code in playground" option for code blocks */ html` <span
                  class="code_external_link"
              >
                  <i
                      class="zulip-icon zulip-icon-external-link playground-links-popover-container"
                  ></i>
              </span>`
            : ""}
    </div> `;
    return to_html(out);
}
