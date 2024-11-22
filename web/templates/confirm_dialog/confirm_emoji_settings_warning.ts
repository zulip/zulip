import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_emoji_settings_warning(context) {
    const out = html`<div class="rendered_markdown">
        <p>
            ${$html_t(
                {
                    defaultMessage:
                        "There is a default emoji with this name. Do you want to override it with a custom emoji? The name <code>:{emoji_name}:</code> will no longer work to access the default emoji.",
                },
                {emoji_name: context.emoji_name},
            )}
        </p>
    </div> `;
    return to_html(out);
}
