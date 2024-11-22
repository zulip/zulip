import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_stream_members_table(context) {
    const out = html`<div
        class="subscriber_list_container"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="subscriber_list_loading_indicator"></div>
        <table id="stream_members_list" class="subscriber-list table table-striped">
            <thead class="table-sticky-headers">
                <th data-sort="alphabetic" data-sort-prop="full_name">
                    ${$t({defaultMessage: "Name"})}
                </th>
                <th class="settings-email-column" data-sort="email">
                    ${$t({defaultMessage: "Email"})}
                </th>
                ${to_bool(context.can_remove_subscribers)
                    ? html` <th>${$t({defaultMessage: "Actions"})}</th> `
                    : ""}
            </thead>
            <tbody
                class="subscriber_table"
                data-empty="${$t({defaultMessage: "This channel has no subscribers."})}"
                data-search-results-empty="${$t({
                    defaultMessage: "No channel subscribers match your current filter.",
                })}"
            ></tbody>
        </table>
    </div> `;
    return to_html(out);
}
