import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";

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
            ${{
                __html: render_action_button({
                    hidden: true,
                    id: "emoji_image_clear_button",
                    intent: "danger",
                    attention: "quiet",
                    label: $t({defaultMessage: "Clear image"}),
                }),
            }}
            ${{
                __html: render_action_button({
                    id: "emoji_upload_button",
                    intent: "brand",
                    attention: "quiet",
                    label: $t({defaultMessage: "Upload image or GIF"}),
                }),
            }}
            <div style="display: none;" id="emoji_preview_text">
                ${$t({defaultMessage: "Preview:"})}
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
                autocomplete="off"
                placeholder="${$t({defaultMessage: "leafy green vegetable"})}"
            />
        </div>
    </form> `;
    return to_html(out);
}
