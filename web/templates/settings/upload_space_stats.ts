import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_upload_space_stats(context) {
    const out = html`<span>
        ${to_bool(context.show_upgrade_message)
            ? html`
                  <a href="/upgrade/" class="upgrade-tip" target="_blank" rel="noopener noreferrer">
                      ${context.upload_quota_string}
                      ${$t({defaultMessage: "Upgrade for more space."})}
                  </a>
              `
            : html` <div class="tip">${context.upload_quota_string}</div> `}</span
    > `;
    return to_html(out);
}
