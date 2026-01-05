import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";

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
        ${{
            __html: render_action_button({
                id: "open-add-alert-word-modal",
                intent: "brand",
                attention: "quiet",
                label: $t({defaultMessage: "Add alert word"}),
            }),
        }}
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Alert words"})}</h3>
        </div>
        <div class="banner-wrapper" id="alert_word_status"></div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <tr>
                        <th data-sort="alphabetic" data-sort-prop="word">
                            ${$t({defaultMessage: "Word"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                    </tr>
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
