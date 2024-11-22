import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_add_subscribers_form from "./add_subscribers_form.ts";

export default function render_new_stream_users() {
    const out = html`<div class="subscriber_list_settings">
            <div class="subscriber_list_add float-left">
                ${{__html: render_add_subscribers_form({hide_add_button: true})}}
            </div>
            <br />
        </div>

        <div class="create_stream_subscriber_list_header">
            <h4 class="stream_setting_subsection_title">
                ${$t({defaultMessage: "Subscribers preview"})}
            </h4>
            <input
                class="add-user-list-filter filter_text_input"
                name="user_list_filter"
                type="text"
                autocomplete="off"
                placeholder="${$t({defaultMessage: "Filter subscribers"})}"
            />
        </div>

        <div class="subscriber-list-box">
            <div class="subscriber_list_container" data-simplebar data-simplebar-tab-index="-1">
                <table class="subscriber-list table table-striped">
                    <thead class="table-sticky-headers">
                        <th data-sort="alphabetic" data-sort-prop="full_name">
                            ${$t({defaultMessage: "Name"})}
                        </th>
                        <th class="settings-email-column" data-sort="email">
                            ${$t({defaultMessage: "Email"})}
                        </th>
                        <th>${$t({defaultMessage: "Action"})}</th>
                    </thead>
                    <tbody
                        id="create_stream_subscribers"
                        class="subscriber_table"
                        data-empty="${$t({defaultMessage: "This channel has no subscribers."})}"
                        data-search-results-empty="${$t({
                            defaultMessage: "No channel subscribers match your current filter.",
                        })}"
                    ></tbody>
                </table>
            </div>
        </div> `;
    return to_html(out);
}
