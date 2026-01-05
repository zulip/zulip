import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_filter_text_input from "./filter_text_input.ts";

export default function render_bot_list(context) {
    const out = html`<div class="settings_panel_list_header">
            <h3>${context.section_title}</h3>
            <div class="alert-notification"></div>
            <div class="bot-filters">
                ${{__html: render_dropdown_widget({widget_name: context.dropdown_widget_name})}}
                ${{
                    __html: render_filter_text_input({
                        aria_label: $t({defaultMessage: "Filter bots"}),
                        placeholder: $t({defaultMessage: "Filter"}),
                    }),
                }}
            </div>
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <tr>
                        <th class="active" data-sort="alphabetic" data-sort-prop="full_name">
                            ${$t({defaultMessage: "Name"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="settings-email-column" data-sort="email">
                            ${$t({defaultMessage: "Email"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="user_role" data-sort="role">
                            ${$t({defaultMessage: "Role"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th data-sort="bot_owner">
                            ${$t({defaultMessage: "Owner"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th data-sort="alphabetic" data-sort-prop="bot_type" class="bot_type">
                            ${$t({defaultMessage: "Bot type"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                    </tr>
                </thead>
                <tbody
                    id="admin_${context.section_name}_table"
                    class="admin_bot_table"
                    data-empty="${context.section_name === "all_bots"
                        ? $t({defaultMessage: "There are no active bots in this organization."})
                        : $t({defaultMessage: "You have no active bots"})}"
                    data-search-results-empty="${context.section_name === "all_bots"
                        ? $t({defaultMessage: "No bots match your current filter."})
                        : $t({defaultMessage: "None of your bots match your current filter."})}"
                ></tbody>
            </table>
        </div>
        <div id="admin_page_${context.section_name}_loading_indicator"></div> `;
    return to_html(out);
}
