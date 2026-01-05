import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_filter_text_input from "./filter_text_input.ts";

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
        ${{
            __html: render_action_button({
                hidden: !to_bool(context.can_add_emojis),
                label: $t({defaultMessage: "Add a new emoji"}),
                intent: "brand",
                attention: "quiet",
                id: "add-custom-emoji-button",
            }),
        }}
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Custom emoji"})}</h3>
            ${{
                __html: render_filter_text_input({
                    aria_label: $t({defaultMessage: "Filter emoji"}),
                    placeholder: $t({defaultMessage: "Filter"}),
                }),
            }}
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table admin_emoji_table">
                <thead class="table-sticky-headers">
                    <tr>
                        <th class="active" data-sort="alphabetic" data-sort-prop="name">
                            ${$t({defaultMessage: "Name"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="image">${$t({defaultMessage: "Image"})}</th>
                        <th class="image" data-sort="author_full_name">
                            ${$t({defaultMessage: "Author"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                    </tr>
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
