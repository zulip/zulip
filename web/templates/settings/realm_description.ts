import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import {postprocess_content} from "../../src/postprocess_content.ts";

export default function render_realm_description(context) {
    const out = html`<div class="input-group admin-realm">
        <label for="id_realm_description" class="settings-field-label">
            ${$t({defaultMessage: "Organization description"})}
        </label>
        ${to_bool(context.is_admin)
            ? html`
                  <textarea
                      id="id_realm_description"
                      name="realm_description"
                      class="admin-realm-description setting-widget prop-element settings-textarea"
                      maxlength="1000"
                      data-setting-widget-type="string"
                  >
${context.realm_description_text}</textarea
                  >
              `
            : html`
                  <div class="admin-realm-description settings-highlight-box rendered_markdown">
                      ${{__html: postprocess_content(context.realm_description_html)}}
                  </div>
              `}
    </div> `;
    return to_html(out);
}
