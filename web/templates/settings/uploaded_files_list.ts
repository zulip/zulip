import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

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
                        class="hidden-attachment-download"
                        download
                    ></a>
                    ${{
                        __html: render_icon_button({
                            ["data-tippy-content"]: $t({defaultMessage: "Download"}),
                            custom_classes: "tippy-zulip-delayed-tooltip download-attachment",
                            intent: "info",
                            icon: "download",
                        }),
                    }}
                </span>
                <span class="edit-attachment-buttons">
                    ${{
                        __html: render_icon_button({
                            ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                            intent: "danger",
                            custom_classes: "tippy-zulip-delayed-tooltip delete remove-attachment",
                            icon: "trash",
                        }),
                    }}
                </span>
            </td>
        </tr> `)(context.attachment);
    return to_html(out);
}
