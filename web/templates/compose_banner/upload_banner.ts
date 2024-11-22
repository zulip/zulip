import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_upload_banner(context) {
    const out = html`<div
        class="upload_banner file_${context.file_id} main-view-banner ${context.banner_type}"
    >
        <div class="moving_bar"></div>
        <p class="upload_msg banner_content">${context.banner_text}</p>
        ${to_bool(context.is_upload_process_tracker)
            ? html`
                  <button class="upload_banner_cancel_button">
                      ${$t({defaultMessage: "Cancel"})}
                  </button>
              `
            : ""}
        <a role="button" class="zulip-icon zulip-icon-close main-view-banner-close-button"></a>
    </div> `;
    return to_html(out);
}
