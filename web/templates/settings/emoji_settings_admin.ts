import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_emoji_settings_admin(context) {
    const out = html`<div id="emoji-settings" data-name="emoji-settings" class="settings-section">
        <div class="emoji-settings-tip-container ${to_bool(context.can_add_emojis) ? "hide" : ""}">
            <div class="tip">
                ${$t({defaultMessage: "You do not have permission to add custom emoji."})}
            </div>
        </div>
        <p class="add-emoji-text ${!to_bool(context.can_add_emojis) ? "hide" : ""}">
            ${$t(
                {defaultMessage: "Add extra emoji for members of the {realm_name} organization."},
                {realm_name: context.realm_name},
            )}
        </p>
        <button
            id="add-custom-emoji-button"
            class="button rounded sea-green ${!to_bool(context.can_add_emojis) ? "hide" : ""}"
        >
            ${$t({defaultMessage: "Add a new emoji"})}
        </button>

        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Custom emoji"})}</h3>
            <input
                type="text"
                class="search filter_text_input"
                placeholder="${$t({defaultMessage: "Filter emoji"})}"
                aria-label="${$t({defaultMessage: "Filter emoji"})}"
            />
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table admin_emoji_table">
                <thead class="table-sticky-headers">
                    <th class="active" data-sort="alphabetic" data-sort-prop="name">
                        ${$t({defaultMessage: "Name"})}
                    </th>
                    <th class="image">${$t({defaultMessage: "Image"})}</th>
                    <th class="image" data-sort="author_full_name">
                        ${$t({defaultMessage: "Author"})}
                    </th>
                    <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                </thead>
                <tbody
                    id="admin_emoji_table"
                    data-empty="${$t({defaultMessage: "There are no custom emoji."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No custom emojis match your current filter.",
                    })}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
