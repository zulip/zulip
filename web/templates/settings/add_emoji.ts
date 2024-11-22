import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_add_emoji() {
    const out = html`<form id="add-custom-emoji-form">
        <div>
            <input
                type="file"
                name="emoji_file_input"
                class="notvisible"
                id="emoji_file_input"
                value="${$t({defaultMessage: "Upload image or GIF"})}"
            />
            <button
                type="button"
                class="button white rounded"
                style="display: none;"
                id="emoji_image_clear_button"
            >
                ${$t({defaultMessage: "Clear image"})}
            </button>
            <button type="button" class="button rounded" id="emoji_upload_button">
                ${$t({defaultMessage: "Upload image or GIF"})}
            </button>
            <div style="display: none;" id="emoji_preview_text">
                Preview:
                <i id="emoji_placeholder_icon" class="fa fa-file-image-o" aria-hidden="true"></i
                ><img class="emoji" id="emoji_preview_image" src="" />
            </div>
            <div id="emoji-file-name"></div>
        </div>
        <div id="emoji_file_input_error" class="text-error"></div>
        <div class="emoji_name_input">
            <label for="emoji_name" class="modal-field-label"
                >${$t({defaultMessage: "Emoji name"})}</label
            >
            <input
                type="text"
                name="name"
                id="emoji_name"
                class="modal_text_input"
                placeholder="${$t({defaultMessage: "leafy green vegetable"})}"
            />
        </div>
    </form> `;
    return to_html(out);
}
