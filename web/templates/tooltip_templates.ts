import {html, to_html} from "../shared/src/html.ts";
import {tooltip_hotkey_hints} from "../src/common.ts";
import {$t} from "../src/i18n.ts";

export default function render_tooltip_templates() {
    const out = html`<template id="view-user-card-tooltip-template">
            ${$t({defaultMessage: "View user card"})} ${tooltip_hotkey_hints("U")}
        </template>
        <template id="view-bot-card-tooltip-template">
            ${$t({defaultMessage: "View bot card"})} ${tooltip_hotkey_hints("U")}
        </template>
        <template id="scroll-to-bottom-button-tooltip-template">
            ${$t({defaultMessage: "Scroll to bottom"})} ${tooltip_hotkey_hints("End")}
        </template>
        <template id="compose_reply_message_button_tooltip_template">
            ${$t({defaultMessage: "Reply to selected message"})} ${tooltip_hotkey_hints("R")}
        </template>
        <template id="compose_reply_selected_topic_button_tooltip_template">
            ${$t({defaultMessage: "Reply to selected conversation"})} ${tooltip_hotkey_hints("R")}
        </template>
        <template id="left_bar_compose_mobile_button_tooltip_template">
            ${$t({defaultMessage: "Start new conversation"})}
        </template>
        <template id="new_topic_message_button_tooltip_template">
            ${$t({defaultMessage: "New topic"})} ${tooltip_hotkey_hints("C")}
        </template>
        <template id="new_stream_message_button_tooltip_template">
            ${$t({defaultMessage: "New channel message"})} ${tooltip_hotkey_hints("C")}
        </template>
        <template id="new_direct_message_button_tooltip_template">
            ${$t({defaultMessage: "New direct message"})} ${tooltip_hotkey_hints("X")}
        </template>
        <template id="compose_close_tooltip_template">
            ${$t({defaultMessage: "Cancel compose"})} ${tooltip_hotkey_hints("Esc")}
        </template>
        <template id="compose_close_and_save_tooltip_template">
            ${$t({defaultMessage: "Cancel compose and save draft"})} ${tooltip_hotkey_hints("Esc")}
        </template>
        <template id="send-enter-tooltip-template">
            ${$t({defaultMessage: "Send"})} ${tooltip_hotkey_hints("Enter")}
        </template>
        <template id="send-ctrl-enter-tooltip-template">
            ${$t({defaultMessage: "Send"})} ${tooltip_hotkey_hints("Ctrl", "Enter")}
        </template>
        <template id="preview-tooltip">
            ${$t({defaultMessage: "Preview"})} ${tooltip_hotkey_hints("Alt", "P")}
        </template>
        <template id="add-global-time-tooltip">
            <div>
                <div>${$t({defaultMessage: "Add global time"})}</div>
                <div class="tooltip-inner-content italic">
                    ${$t({defaultMessage: "Everyone sees global times in their own time zone."})}
                </div>
            </div>
        </template>
        <template id="add-poll-tooltip">
            <div>
                <span>${$t({defaultMessage: "Add poll"})}</span><br />
                <span class="tooltip-inner-content italic"
                    >${$t({defaultMessage: "A poll must be an entire message."})}</span
                >
            </div>
        </template>
        <template id="add-saved-snippet-tooltip">
            ${$t({defaultMessage: "Add saved snippet"})}
        </template>
        <template id="link-tooltip">
            ${$t({defaultMessage: "Link"})} ${tooltip_hotkey_hints("Ctrl", "Shift", "L")}
        </template>
        <template id="bold-tooltip">
            ${$t({defaultMessage: "Bold"})} ${tooltip_hotkey_hints("Ctrl", "B")}
        </template>
        <template id="italic-tooltip">
            ${$t({defaultMessage: "Italic"})} ${tooltip_hotkey_hints("Ctrl", "I")}
        </template>
        <template id="delete-draft-tooltip-template">
            ${$t({defaultMessage: "Delete draft"})} ${tooltip_hotkey_hints("Backspace")}
        </template>
        <template id="restore-draft-tooltip-template">
            ${$t({defaultMessage: "Restore draft"})} ${tooltip_hotkey_hints("Enter")}
        </template>
        <template id="gear-menu-tooltip-template">
            ${$t({defaultMessage: "Main menu"})} ${tooltip_hotkey_hints("G")}
        </template>
        <template id="personal-menu-tooltip-template">
            ${$t({defaultMessage: "Personal menu"})} ${tooltip_hotkey_hints("G", "→")}
        </template>
        <template id="help-menu-tooltip-template">
            ${$t({defaultMessage: "Help menu"})} ${tooltip_hotkey_hints("G", "←")}
        </template>
        <template id="automatic-theme-template">
            <div>
                <div>${$t({defaultMessage: "Automatic theme"})}</div>
                <div class="tooltip-inner-content italic">
                    ${$t({defaultMessage: "Follows system settings."})}
                </div>
            </div>
        </template>
        <template id="all-message-tooltip-template">
            <div class="views-tooltip-container" data-view-code="all_messages">
                <div>${$t({defaultMessage: "Combined feed"})}</div>
                <div class="tooltip-inner-content views-tooltip-home-view-note italic hide">
                    ${$t({defaultMessage: "This is your home view."})}
                </div>
            </div>
            ${tooltip_hotkey_hints("A")}
        </template>
        <template id="recent-conversations-tooltip-template">
            <div class="views-tooltip-container" data-view-code="recent_topics">
                <div>${$t({defaultMessage: "Recent conversations"})}</div>
                <div class="tooltip-inner-content views-tooltip-home-view-note italic hide">
                    ${$t({defaultMessage: "This is your home view."})}
                </div>
            </div>
            ${tooltip_hotkey_hints("T")}
        </template>
        <template id="starred-message-tooltip-template">
            <div class="views-tooltip-container">
                <div>${$t({defaultMessage: "Starred messages"})}</div>
            </div>
            ${tooltip_hotkey_hints("*")}
        </template>
        <template id="my-reactions-tooltip-template">
            <div class="views-tooltip-container" data-view-code="recent_topics">
                <div>${$t({defaultMessage: "Reactions to your messages"})}</div>
            </div>
        </template>
        <template id="inbox-tooltip-template">
            <div class="views-tooltip-container" data-view-code="inbox">
                <div>${$t({defaultMessage: "Inbox"})}</div>
                <div class="tooltip-inner-content views-tooltip-home-view-note italic hide">
                    ${$t({defaultMessage: "This is your home view."})}
                </div>
            </div>
            ${tooltip_hotkey_hints("Shift", "I")}
        </template>
        <template id="drafts-tooltip-template">
            ${$t({defaultMessage: "Drafts"})} ${tooltip_hotkey_hints("D")}
        </template>
        <template id="show-all-direct-messages-template">
            ${$t({defaultMessage: "Direct message feed"})} ${tooltip_hotkey_hints("Shift", "P")}
        </template>
        <template id="mentions-tooltip-template"> ${$t({defaultMessage: "Mentions"})} </template>
        <template id="starred-tooltip-template">
            ${$t({defaultMessage: "Starred messages"})}
        </template>
        <template id="filter-streams-tooltip-template">
            ${$t({defaultMessage: "Filter channels"})} ${tooltip_hotkey_hints("Q")}
        </template>
        <template id="message-expander-tooltip-template">
            ${$t({defaultMessage: "Show more"})} ${tooltip_hotkey_hints("-")}
        </template>
        <template id="message-condenser-tooltip-template">
            ${$t({defaultMessage: "Show less"})} ${tooltip_hotkey_hints("-")}
        </template>
        <template id="edit-content-tooltip-template">
            ${$t({defaultMessage: "Edit message"})} ${tooltip_hotkey_hints("E")}
        </template>
        <template id="move-message-tooltip-template">
            ${$t({defaultMessage: "Move message"})} ${tooltip_hotkey_hints("M")}
        </template>
        <template id="add-emoji-tooltip-template">
            ${$t({defaultMessage: "Add emoji reaction"})} ${tooltip_hotkey_hints(":")}
        </template>
        <template id="message-actions-tooltip-template">
            ${$t({defaultMessage: "Message actions"})} ${tooltip_hotkey_hints("I")}
        </template>
        <template id="dismiss-failed-send-button-tooltip-template">
            <div>
                <div>${$t({defaultMessage: "Dismiss failed message"})}</div>
                <div class="italic tooltip-inner-content">
                    ${$t({defaultMessage: "This content remains saved in your drafts."})}
                </div>
            </div>
        </template>
        <template id="slow-send-spinner-tooltip-template">
            <div>
                <div>${$t({defaultMessage: "Sending…"})}</div>
                <div class="italic">
                    ${$t({
                        defaultMessage:
                            "This message will remain saved in your drafts until it is successfully sent.",
                    })}
                </div>
            </div>
        </template>
        <template id="star-message-tooltip-template">
            <div class="starred-status">${$t({defaultMessage: "Star this message"})}</div>
            ${tooltip_hotkey_hints("Ctrl", "S")}
        </template>
        <template id="unstar-message-tooltip-template">
            <div class="starred-status">${$t({defaultMessage: "Unstar this message"})}</div>
            ${tooltip_hotkey_hints("Ctrl", "S")}
        </template>
        <template id="search-query-tooltip-template">
            ${$t({defaultMessage: "Search"})} ${tooltip_hotkey_hints("/")}
        </template>
        <template id="show-left-sidebar-tooltip-template">
            ${$t({defaultMessage: "Show left sidebar"})} ${tooltip_hotkey_hints("Q")}
        </template>
        <template id="hide-left-sidebar-tooltip-template">
            ${$t({defaultMessage: "Hide left sidebar"})}
        </template>
        <template id="show-userlist-tooltip-template">
            ${$t({defaultMessage: "Show user list"})} ${tooltip_hotkey_hints("W")}
        </template>
        <template id="hide-userlist-tooltip-template">
            ${$t({defaultMessage: "Hide user list"})}
        </template>
        <template id="topic-unmute-tooltip-template">
            ${$t({defaultMessage: "Unmute topic"})} ${tooltip_hotkey_hints("Shift", "M")}
        </template>
        <template id="topic-mute-tooltip-template">
            ${$t({defaultMessage: "Mute topic"})} ${tooltip_hotkey_hints("Shift", "M")}
        </template>
        <template id="restore-scheduled-message-tooltip-template">
            ${$t({defaultMessage: "Edit and reschedule message"})} ${tooltip_hotkey_hints("Enter")}
        </template>
        <template id="delete-scheduled-message-tooltip-template">
            ${$t({defaultMessage: "Delete scheduled message"})} ${tooltip_hotkey_hints("Backspace")}
        </template>
        <template id="create-new-stream-tooltip-template">
            ${$t({defaultMessage: "Create new channel"})} ${tooltip_hotkey_hints("N")}
        </template>
        <template id="show-subscribe-tooltip-template">
            ${$t({defaultMessage: "Subscribe to this channel"})}
            ${tooltip_hotkey_hints("Shift", "S")}
        </template>
        <template id="show-unsubscribe-tooltip-template">
            ${$t({defaultMessage: "Unsubscribe from this channel"})}
            ${tooltip_hotkey_hints("Shift", "S")}
        </template>
        <template id="view-stream-tooltip-template">
            ${$t({defaultMessage: "View channel"})} ${tooltip_hotkey_hints("Shift", "V")}
        </template>
        <template id="mobile-push-notification-tooltip-template">
            ${$t({defaultMessage: "Mobile push notifications are not enabled on this server."})}
        </template> `;
    return to_html(out);
}
