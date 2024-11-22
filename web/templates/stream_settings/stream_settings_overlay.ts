import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_stream_creation_form from "./stream_creation_form.ts";

export default function render_stream_settings_overlay(context) {
    const out = html`<div id="subscription_overlay" class="overlay" data-overlay="subscriptions">
        <div class="flex overlay-content">
            <div class="subscriptions-container overlay-container">
                <div class="subscriptions-header">
                    <div class="fa fa-chevron-left"></div>
                    <span class="subscriptions-title">${$t({defaultMessage: "Channels"})}</span>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                </div>
                <div class="left">
                    <div class="list-toggler-container">
                        <div id="add_new_subscription">
                            ${to_bool(context.can_create_streams)
                                ? html`
                                      <button
                                          class="create_stream_button create_stream_plus_button tippy-zulip-delayed-tooltip"
                                          data-tooltip-template-id="create-new-stream-tooltip-template"
                                          data-tippy-placement="bottom"
                                      >
                                          <span class="create_button_plus_sign">+</span>
                                      </button>
                                  `
                                : ""}
                            <div class="float-clear"></div>
                        </div>
                    </div>
                    <div class="input-append stream_name_search_section" id="stream_filter">
                        <input
                            type="text"
                            name="stream_name"
                            id="search_stream_name"
                            class="filter_text_input"
                            autocomplete="off"
                            placeholder="${$t({defaultMessage: "Filter channels"})}"
                            value=""
                        />
                        <button
                            type="button"
                            class="bootstrap-btn clear_search_button"
                            id="clear_search_stream_name"
                        >
                            <i class="fa fa-remove" aria-hidden="true"></i>
                        </button>
                    </div>
                    <div class="no-streams-to-show">
                        <div class="subscribed_streams_tab_empty_text">
                            <span class="settings-empty-option-text">
                                ${$t({defaultMessage: "You are not subscribed to any channels."})}
                                ${to_bool(context.can_view_all_streams)
                                    ? html`
                                          <a href="#channels/all"
                                              >${$t({defaultMessage: "View all channels"})}</a
                                          >
                                      `
                                    : ""}
                            </span>
                        </div>
                        <div class="not_subscribed_streams_tab_empty_text">
                            <span class="settings-empty-option-text">
                                ${$t({defaultMessage: "No channels to show."})}
                                <a href="#channels/all"
                                    >${$t({defaultMessage: "View all channels"})}</a
                                >
                            </span>
                        </div>
                        <div class="no_stream_match_filter_empty_text">
                            <span class="settings-empty-option-text">
                                ${$t({defaultMessage: "No channels match your filter."})}
                            </span>
                        </div>
                        <div class="all_streams_tab_empty_text">
                            <span class="settings-empty-option-text">
                                ${$t({
                                    defaultMessage:
                                        "There are no channels you can view in this organization.",
                                })}
                                ${to_bool(context.can_create_streams)
                                    ? html`
                                          <a href="#channels/new"
                                              >${$t({defaultMessage: "Create a channel"})}</a
                                          >
                                      `
                                    : ""}
                            </span>
                        </div>
                    </div>
                    <div class="streams-list" data-simplebar data-simplebar-tab-index="-1"></div>
                </div>
                <div class="right">
                    <div class="display-type">
                        <div id="stream_settings_title" class="stream-info-title">
                            ${$t({defaultMessage: "Channel settings"})}
                        </div>
                    </div>
                    <div class="nothing-selected">
                        <div class="stream-info-banner"></div>
                        <div class="create-stream-button-container">
                            <button
                                type="button"
                                class="create_stream_button animated-purple-button"
                                ${!to_bool(context.can_create_streams) ? "disabled" : ""}
                            >
                                ${$t({defaultMessage: "Create channel"})}
                            </button>
                            ${!to_bool(context.can_create_streams)
                                ? html`
                                      <span class="settings-empty-option-text">
                                          ${$t({
                                              defaultMessage:
                                                  "You do not have permission to create channels.",
                                          })}
                                      </span>
                                  `
                                : ""}
                        </div>
                    </div>
                    <div
                        id="stream_settings"
                        class="settings"
                        data-simplebar
                        data-simplebar-tab-index="-1"
                        data-simplebar-auto-hide="false"
                    >
                        ${/* edit stream here */ ""}
                    </div>
                    ${{__html: render_stream_creation_form(context)}}
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
