import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_long_paste_options(context) {
    const out = html`<div class="main-view-banner ${context.banner_type} ${context.classname}">
        <div class="main-view-banner-elements-wrapper">
            ${to_bool(context.show_paste_button)
                ? html`
                      <div class="banner_content">
                          ${$t({defaultMessage: "Paste text directly or convert to a file?"})}
                      </div>
                      <button class="main-view-banner-action-button paste-to-compose">
                          ${$t({defaultMessage: "Paste"})}
                      </button>
                      <button
                          class="main-view-banner-action-button convert-to-file secondary-button right_edge"
                      >
                          ${$t({defaultMessage: "Convert"})}
                      </button>
                  `
                : html`
                      <div class="banner_content">
                          ${$t({
                              defaultMessage: "Do you want to convert the pasted text into a file?",
                          })}
                      </div>
                      <button class="main-view-banner-action-button convert-to-file right_edge">
                          ${$t({defaultMessage: "Yes, convert"})}
                      </button>
                  `}
        </div>
        <a role="button" class="zulip-icon zulip-icon-close main-view-banner-close-button"></a>
    </div> `;
    return to_html(out);
}
