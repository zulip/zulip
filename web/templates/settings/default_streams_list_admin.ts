import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_default_streams_list_admin(context) {
    const out = html`<div
        id="admin-default-channels-list"
        class="settings-section"
        data-name="default-channels-list"
    >
        <p>
            ${$t({
                defaultMessage:
                    "Configure the default channels new users are subscribed to when joining your organization.",
            })}
        </p>

        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Default channels"})}</h3>
            <div class="add_default_streams_button_container">
                ${to_bool(context.is_admin)
                    ? html`
                          <button
                              type="submit"
                              id="show-add-default-streams-modal"
                              class="button rounded sea-green"
                          >
                              ${$t({defaultMessage: "Add channel"})}
                          </button>
                      `
                    : ""}
                <input
                    type="text"
                    class="search filter_text_input"
                    placeholder="${$t({defaultMessage: "Filter default channels"})}"
                    aria-label="${$t({defaultMessage: "Filter channels"})}"
                />
            </div>
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th class="active" data-sort="alphabetic" data-sort-prop="name">
                        ${$t({defaultMessage: "Name"})}
                    </th>
                    ${to_bool(context.is_admin)
                        ? html` <th class="actions">${$t({defaultMessage: "Actions"})}</th> `
                        : ""}
                </thead>
                <tbody
                    data-empty="${$t({defaultMessage: "There are no default channels."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No default channels match your current filter.",
                    })}"
                    id="admin_default_streams_table"
                    class="admin_default_stream_table"
                ></tbody>
            </table>
        </div>

        <div id="admin_page_default_streams_loading_indicator"></div>
    </div> `;
    return to_html(out);
}
