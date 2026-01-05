import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_dropdown_widget from "../dropdown_widget.ts";

export default function render_edit_channel_folder_modal(context) {
    const out = html`<div id="channel_folder_banner" class="banner-wrapper"></div>
        <div>
            <label for="edit_channel_folder_name" class="modal-field-label">
                ${$t({defaultMessage: "Channel folder name"})}
            </label>
            <input
                type="text"
                id="edit_channel_folder_name"
                class="modal_text_input"
                name="channel_folder_name"
                maxlength="${context.max_channel_folder_name_length}"
                value="${context.name}"
            />
        </div>
        <div>
            <label for="edit_channel_folder_description" class="modal-field-label">
                ${$t({defaultMessage: "Description"})}
            </label>
            <textarea
                id="edit_channel_folder_description"
                class="modal-textarea"
                name="channel_folder_description"
                maxlength="${context.max_channel_folder_description_length}"
            >
${context.description}</textarea
            >
        </div>
        <div>
            <div>
                <h3 class="folder-channels-list-header">${$t({defaultMessage: "Channels"})}</h3>
            </div>
            <div class="stream-list-container" data-folder-id="${context.folder_id}">
                <div
                    class="stream-search-container filter-input has-input-icon has-input-button input-element-wrapper"
                >
                    <i class="input-icon zulip-icon zulip-icon-search" aria-hidden="true"></i>
                    <input
                        type="text"
                        class="input-element stream-search"
                        placeholder="${$t({defaultMessage: "Filter"})}"
                    />
                    <button
                        type="button"
                        class="input-button input-close-filter-button icon-button icon-button-square icon-button-neutral "
                    >
                        <i class="zulip-icon zulip-icon-close" aria-hidden="true"></i>
                    </button>
                </div>
                <div
                    class="edit-channel-folder-stream-list"
                    data-simplebar
                    data-simplebar-tab-index="-1"
                >
                    <ul
                        class="folder-stream-list"
                        data-empty="${$t({defaultMessage: "No channel in channel folder."})}"
                        data-search-results-empty="${$t({defaultMessage: "No matching channels."})}"
                    ></ul>
                </div>
            </div>
        </div>
        <div>
            <div>
                <h3 class="folder-channels-list-header">
                    ${$t({defaultMessage: "Add a channel"})}
                </h3>
            </div>
            <div class="add_channel_folder_widget">
                ${{__html: render_dropdown_widget({widget_name: "add_channel_folder"})}}
                ${{
                    __html: render_action_button({
                        ["aria-label"]: $t({defaultMessage: "Add"}),
                        intent: "brand",
                        attention: "quiet",
                        custom_classes: "add-channel-button",
                        label: $t({defaultMessage: "Add"}),
                    }),
                }}
            </div>
        </div> `;
    return to_html(out);
}
