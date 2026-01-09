import $ from "jquery";
import render_poll_widget from "../templates/widgets/poll_widget.hbs";
import Handlebars from "handlebars/runtime";

/*
 * Showcase does not initialize i18n because we configure our own page params.
 * So we stub out translation helpers.
 */
if (!Handlebars.helpers["t"]) {
    Handlebars.registerHelper("t", (str: string) => str);
}

import type {PollWidgetOutboundData} from "./poll_data.ts";
import * as poll_widget from "./poll_widget.ts";

// Setting base html
document.body.innerHTML = ` 
<div hidden id="page-params" data-params='{"page_type":"home","development_environment":"true"}'></div>,
<div class="app">
            <div class="app-main">
                <div class="column-left" id="left-sidebar-container"></div>
                <div class="column-middle">
                    <div class="column-middle-inner">
                        <div id="recent_view">
                            <div class="recent_view_container">
                                <div id="recent_view_table"></div>
                            </div>
                            <table id="recent-view-content-table">
                                <tbody data-empty="No conversations match your filters." id="recent-view-content-tbody"></tbody>
                            </table>
                            <div id="recent_view_bottom_whitespace">
                                <div class="bottom-messages-logo">
                                    <svg class="messages-logo-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 773.12 773.12">
                                        <circle cx="386.56" cy="386.56" r="386.56"/>
                                        <path d="M566.66 527.25c0 33.03-24.23 60.05-53.84 60.05H260.29c-29.61 0-53.84-27.02-53.84-60.05 0-20.22 9.09-38.2 22.93-49.09l134.37-120c2.5-2.14 5.74 1.31 3.94 4.19l-49.29 98.69c-1.38 2.76.41 6.16 3.25 6.16h191.18c29.61 0 53.83 27.03 53.83 60.05zm0-281.39c0 20.22-9.09 38.2-22.93 49.09l-134.37 120c-2.5 2.14-5.74-1.31-3.94-4.19l49.29-98.69c1.38-2.76-.41-6.16-3.25-6.16H260.29c-29.61 0-53.84-27.02-53.84-60.05s24.23-60.05 53.84-60.05h252.54c29.61 0 53.83 27.02 53.83 60.05z"/>
                                    </svg>
                                </div>
                                <div id="recent_view_loading_messages_indicator"></div>
                            </div>
                            <!-- Don't show the banner until we have some messages loaded. -->
                            <div class="recent-view-load-more-container main-view-banner info notvisible">
                                <div class="last-fetched-message banner_content">This view is still loading messages.</div>
                                <button class="fetch-messages-button main-view-banner-action-button right_edge notvisible">
                                    <span class="loading-indicator"></span>
                                    <span class="button-label">Load more</span>
                                </button>
                            </div>
                        </div>
                        <div id="inbox-view" class="no-visible-focus-outlines">
                            <div class="inbox-container">
                                <div id="inbox-pane"></div>
                            </div>
                        </div>
                        <div id="message_feed_container">
                            <div class="message-feed" id="main_div">
                                <div class="top-messages-logo">
                                    <svg class="messages-logo-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 773.12 773.12">
                                        <circle cx="386.56" cy="386.56" r="386.56"/>
                                        <path d="M566.66 527.25c0 33.03-24.23 60.05-53.84 60.05H260.29c-29.61 0-53.84-27.02-53.84-60.05 0-20.22 9.09-38.2 22.93-49.09l134.37-120c2.5-2.14 5.74 1.31 3.94 4.19l-49.29 98.69c-1.38 2.76.41 6.16 3.25 6.16h191.18c29.61 0 53.83 27.03 53.83 60.05zm0-281.39c0 20.22-9.09 38.2-22.93 49.09l-134.37 120c-2.5 2.14-5.74-1.31-3.94-4.19l49.29-98.69c1.38-2.76-.41-6.16-3.25-6.16H260.29c-29.61 0-53.84-27.02-53.84-60.05s24.23-60.05 53.84-60.05h252.54c29.61 0 53.83 27.02 53.83 60.05z"/>
                                    </svg>
                                </div>
                                <div id="loading_older_messages_indicator"></div>
                                <div id="page_loading_indicator"></div>
                                <div id="message_feed_errors_container"></div>
                                <div id="message-lists-container"></div>
                                <div id="scheduled_message_indicator"></div>
                                <div id="mark_read_on_scroll_state_banner"></div>
                                <div id="typing_notifications"></div>
                                <div id="mark_read_on_scroll_state_banner_place_holder"></div>
                                <div id="bottom_whitespace"></div>
                            </div>
                        </div>
                        <div id="compose">
                            <div id="compose-container"></div>
                        </div>
                    </div>
                </div>
                <div class="column-right" id="right-sidebar-container"></div>
                <!--/right sidebar-->
            </div>
        </div>
        <div class="hidden">
            <form id="logout_form" action="/accounts/logout/" method="POST">
                <input type="hidden" name="csrfmiddlewaretoken" value="phOJKH3IYRAnLpa47IkE84skelZWg8emXEVgFZmu5PdMfCXDTerLaN9gqD7SkJWy">
            </form>
        </div>`;

// Middle row classes for some base styling and the `.widget-content` element.
document.querySelector(".column-middle-inner")!.innerHTML = `
<div class="messagebox">
        <div class="messagebox-content ">
            <span class="message_sender">
</span>

<a href="http://zulip.zulipdev.com:9991/#narrow/channel/3-Verona/topic/green.20printer.20was.20skipping.20quickly/near/158" class="message-time">
    <span class="copy-paste-text">&nbsp;</span>
    6:54 PM
</a>


<div class="message_controls no-select">
                <div class="edit_content message_control_button can-move-message" data-tooltip-template-id="move-message-tooltip-template">
            <i class="message-controls-icon zulip-icon zulip-icon-edit edit_content_button edit_message_button" role="button" tabindex="0" aria-label="Edit message (e)"></i>
            <i class="message-controls-icon zulip-icon zulip-icon-move-alt move_message_button edit_message_button" role="button" tabindex="0" aria-label="Move message (m)"></i>
        </div>


<div class="actions_hover message_control_button" data-tooltip-template-id="message-actions-tooltip-template">
    <i class="message-controls-icon message-actions-menu-button zulip-icon zulip-icon-more-vertical-spread" role="button" aria-haspopup="true" tabindex="0" aria-label="Message actions"></i>
</div>

<div class="star_container message_control_button empty-star" data-tooltip-template-id="star-message-tooltip-template">
    <i role="button" tabindex="0" class="message-controls-icon star zulip-icon zulip-icon-star"></i>
</div>
</div>

    <div class="message_content rendered_markdown"><div class="widget-content">
    
<div class="edit-notifications"></div>

<div class="message_length_controller"></div>


        </div>
    </div>`;

document.querySelector(".widget-content")!.innerHTML = render_poll_widget();
const $widget_elem = $(".widget-content");
let poll_callback;
const opts = {
    $elem: $widget_elem,
    callback(data: PollWidgetOutboundData) {
        poll_callback!([{sender_id: 1, data}]);
    },
    message: {
        sender_id: 1,
    },
    extra_data: {
        question: "Where to go?",
        options: ["east", "west"],
    },
};
poll_callback = poll_widget.activate(opts);