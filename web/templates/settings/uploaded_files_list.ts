import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_uploaded_files_list(context) {
    const out = ((attachment) =>
        html`<tr
            class="uploaded_file_row"
            data-attachment-name="${attachment.name}"
            data-attachment-id="${attachment.id}"
        >
            <td>
                <a
                    type="submit"
                    class="tippy-zulip-delayed-tooltip"
                    href="/user_uploads/${attachment.path_id}"
                    target="_blank"
                    rel="noopener noreferrer"
                    data-tippy-content="${$t({defaultMessage: "View file"})}"
                >
                    ${attachment.name}
                </a>
            </td>
            <td>${attachment.create_time_str}</td>
            <td>
                ${to_bool(attachment.messages)
                    ? html`
                          <div class="attachment-messages">
                              ${to_array(attachment.messages).map(
                                  (message) => html`
                                      <a class="ind-message" href="/#narrow/id/${message.id}">
                                          #${message.id}
                                      </a>
                                  `,
                              )}
                          </div>
                      `
                    : ""}
            </td>
            <td class="upload-size">${attachment.size_str}</td>
            <td class="actions">
                <span class="edit-attachment-buttons">
                    <a
                        type="submit"
                        href="/user_uploads/${attachment.path_id}"
                        class="button rounded small sea-green tippy-zulip-delayed-tooltip download-attachment"
                        data-tippy-content="${$t({defaultMessage: "Download"})}"
                        download
                    >
                        <i class="fa fa-download sea-green" aria-hidden="true"></i>
                    </a>
                </span>
                <span class="edit-attachment-buttons">
                    <button
                        type="submit"
                        class="button rounded small delete button-danger remove-attachment tippy-zulip-delayed-tooltip"
                        data-tippy-content="${$t({defaultMessage: "Delete"})}"
                        data-attachment="${attachment.id}"
                    >
                        <i class="fa fa-trash-o" aria-hidden="true"></i>
                    </button>
                </span>
            </td>
        </tr> `)(context.attachment);
    return to_html(out);
}
