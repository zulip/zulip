import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_delete_detached_attachments(context) {
    const out = html`<div>
${to_bool(context.realm_allow_edit_history) ? $html_t({defaultMessage: "The following <z-link>uploaded files</z-link> are no longer attached to any messages. They can still be accessed from this message's edit history. Would you like to delete them entirely?"}, {["z-link"]: (content) => html`<a class="uploaded_files_settings_link" href="/#settings/uploaded-files">${content}</a>`}) : $html_t({defaultMessage: "The following <z-link>uploaded files</z-link> are no longer attached to any messages. Would you like to delete them entirely?"}, {["z-link"]: (content) => html`<a class="uploaded_files_settings_link" href="/#settings/uploaded-files">${content}</a>`})}</div>
<p>
    <ul>
${to_array(context.attachments_list).map(
    (attachment) => html`
        <li>
            <a href="/user_uploads/${attachment.path_id}" rel="noopener noreferrer" target="_blank"
                >${attachment.name}</a
            >
        </li>
    `,
)}    </ul>
</p>
`;
    return to_html(out);
}
