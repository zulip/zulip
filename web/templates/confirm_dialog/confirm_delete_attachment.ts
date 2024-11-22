import {to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_delete_attachment(context) {
    const out = $html_t(
        {
            defaultMessage:
                "<p><strong>{file_name}</strong> will be removed from the messages where it was shared. This action cannot be undone.</p>",
        },
        {file_name: context.file_name},
    );
    return to_html(out);
}
