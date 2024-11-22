import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_alert_word_settings() {
    const out = html`<div id="alert-word-settings" class="settings-section" data-name="alert-words">
        <form id="alert_word_info_box">
            <p class="alert-word-settings-note">
                ${$t({
                    defaultMessage:
                        "Alert words allow you to be notified as if you were @-mentioned when certain words or phrases are used in Zulip. Alert words are not case sensitive.",
                })}
            </p>
        </form>
        <button class="button rounded sea-green" id="open-add-alert-word-modal" type="button">
            ${$t({defaultMessage: "Add alert word"})}
        </button>

        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Alert words"})}</h3>
        </div>
        <div class="alert" id="alert_word_status" role="alert">
            <button
                type="button"
                class="close close-alert-word-status"
                aria-label="${$t({defaultMessage: "Close"})}"
            >
                <span aria-hidden="true">&times;</span>
            </button>
            <span class="alert_word_status_text"></span>
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th data-sort="alphabetic" data-sort-prop="word">
                        ${$t({defaultMessage: "Word"})}
                    </th>
                    <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                </thead>
                <tbody
                    id="alert-words-table"
                    class="alert-words-table"
                    data-empty="${$t({defaultMessage: "There are no current alert words."})}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
