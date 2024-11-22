import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_data_exports_admin(context) {
    const out = html`<div id="data-exports" class="settings-section" data-name="data-exports-admin">
        <h3>
            ${$t({defaultMessage: "Export organization"})}
            ${{__html: render_help_link_widget({link: "/help/export-your-organization"})}}
        </h3>
        <p>
            ${$t({
                defaultMessage:
                    "Your organization’s data will be exported in a format designed for imports into Zulip Cloud or a self-hosted installation of Zulip.",
            })}
            ${$t({
                defaultMessage:
                    "You will be able to export all public data, and (optionally) private data from users who have given their permission.",
            })}
            ${$html_t(
                {defaultMessage: "<z-link>Learn more</z-link> about other data export options."},
                {
                    ["z-link"]: (content) =>
                        html`<a
                            href="/help/export-your-organization"
                            target="_blank"
                            rel="noopener noreferrer"
                            >${content}</a
                        >`,
                },
            )}
        </p>
        <p>
            ${$t({
                defaultMessage:
                    "Depending on the size of your organization, an export can take anywhere from seconds to an hour.",
            })}
        </p>

        ${to_bool(context.is_admin)
            ? html`
                  <div class="alert" id="export_status" role="alert">
                      <span class="export_status_text"></span>
                  </div>
                  <form>
                      <button
                          type="submit"
                          class="button rounded sea-green"
                          id="start-export-button"
                      >
                          ${$t({defaultMessage: "Start export"})}
                      </button>
                  </form>
              `
            : ""}
        <hr />

        <div class="tab-container"></div>

        <div class="export_section" data-export-section="data-exports">
            <div class="settings_panel_list_header">
                <h3>${$t({defaultMessage: "Data exports"})}</h3>
                <input
                    type="hidden"
                    class="search"
                    placeholder="${$t({defaultMessage: "Filter exports"})}"
                    aria-label="${$t({defaultMessage: "Filter exports"})}"
                />
            </div>

            <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
                <table class="table table-striped wrapped-table admin_exports_table">
                    <thead class="table-sticky-headers">
                        <th class="active" data-sort="user">
                            ${$t({defaultMessage: "Requesting user"})}
                        </th>
                        <th>${$t({defaultMessage: "Type"})}</th>
                        <th data-sort="numeric" data-sort-prop="export_time">
                            ${$t({defaultMessage: "Time"})}
                        </th>
                        <th>${$t({defaultMessage: "Status"})}</th>
                        <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                    </thead>
                    <tbody
                        id="admin_exports_table"
                        data-empty="${$t({defaultMessage: "There are no exports."})}"
                    ></tbody>
                </table>
            </div>
        </div>

        <div class="export_section" data-export-section="export-permissions">
            <div class="settings_panel_list_header">
                <h3>${$t({defaultMessage: "Export permissions"})}</h3>
                <div class="user_filters">
                    ${{__html: render_dropdown_widget({widget_name: "filter_by_consent"})}}
                    <input
                        type="text"
                        class="search filter_text_input"
                        placeholder="${$t({defaultMessage: "Filter users"})}"
                        aria-label="${$t({defaultMessage: "Filter users"})}"
                    />
                </div>
            </div>

            <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
                <table class="table table-striped wrapped-table">
                    <thead class="table-sticky-headers">
                        <th class="active" data-sort="full_name">
                            ${$t({defaultMessage: "Name"})}
                        </th>
                        <th>${$t({defaultMessage: "Export permission"})}</th>
                    </thead>
                    <tbody id="admin_export_consents_table"></tbody>
                </table>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
