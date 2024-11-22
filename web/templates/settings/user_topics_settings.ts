import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_user_topics_settings() {
    const out = html`<div id="user-topic-settings" class="settings-section" data-name="topics">
        <p>
            ${$html_t(
                {
                    defaultMessage:
                        "Zulip lets you follow topics you are interested in, and mute topics you want to ignore. You can also <z-automatically-follow>automatically follow</z-automatically-follow> topics you start or participate in, and topics where you're mentioned.",
                },
                {
                    ["z-automatically-follow"]: (content) =>
                        html`<a
                            href="/help/follow-a-topic#automatically-follow-topics"
                            target="_blank"
                            rel="noopener noreferrer"
                            >${content}</a
                        >`,
                },
            )}
        </p>
        <div class="settings_panel_list_header">
            <h3>
                ${$t({defaultMessage: "Topic settings"})}
                ${{__html: render_help_link_widget({link: "/help/topic-notifications"})}}
            </h3>
            ${{
                __html: render_settings_save_discard_widget({
                    show_only_indicator: true,
                    section_name: "user-topics-settings",
                }),
            }}
            <input
                id="user_topics_search"
                class="search filter_text_input"
                type="text"
                placeholder="${$t({defaultMessage: "Filter topics"})}"
                aria-label="${$t({defaultMessage: "Filter topics"})}"
            />
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th data-sort="alphabetic" data-sort-prop="stream">
                        ${$t({defaultMessage: "Channel"})}
                    </th>
                    <th data-sort="alphabetic" data-sort-prop="topic">
                        ${$t({defaultMessage: "Topic"})}
                    </th>
                    <th data-sort="numeric" data-sort-prop="visibility_policy">
                        ${$t({defaultMessage: "Status"})}
                    </th>
                    <th
                        data-sort="numeric"
                        data-sort-prop="date_updated"
                        class="active topic_date_updated"
                    >
                        ${$t({defaultMessage: "Date updated"})}
                    </th>
                </thead>
                <tbody
                    id="user_topics_table"
                    data-empty="${$t({defaultMessage: "You have not configured any topics yet."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No topics match your current filter.",
                    })}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
