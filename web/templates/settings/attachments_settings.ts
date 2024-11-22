import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_attachments_settings() {
    const out = html`<div
        id="attachments-settings"
        class="settings-section"
        data-name="uploaded-files"
    >
        <div id="attachment-stats-holder"></div>
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Your uploads"})}</h3>
            <input
                id="upload_file_search"
                class="search filter_text_input"
                type="text"
                placeholder="${$t({defaultMessage: "Filter uploaded files"})}"
                aria-label="${$t({defaultMessage: "Filter uploads"})}"
            />
        </div>
        <div class="clear-float"></div>
        <div class="alert" id="delete-upload-status"></div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th data-sort="alphabetic" data-sort-prop="name" class="upload-file-name">
                        ${$t({defaultMessage: "File"})}
                    </th>
                    <th class="active upload-date" data-sort="numeric" data-sort-prop="create_time">
                        ${$t({defaultMessage: "Date uploaded"})}
                    </th>
                    <th class="upload-mentioned-in" data-sort="mentioned_in">
                        ${$t({defaultMessage: "Mentioned in"})}
                    </th>
                    <th class="upload-size" data-sort="numeric" data-sort-prop="size">
                        ${$t({defaultMessage: "Size"})}
                    </th>
                    <th class="upload-actions actions">${$t({defaultMessage: "Actions"})}</th>
                </thead>
                <tbody
                    data-empty="${$t({defaultMessage: "You have not uploaded any files."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No uploaded files match your current filter.",
                    })}"
                    id="uploaded_files_table"
                ></tbody>
            </table>
        </div>
        <div id="attachments_loading_indicator"></div>
    </div> `;
    return to_html(out);
}
