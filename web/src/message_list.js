import autosize from "autosize";
import $ from "jquery";

import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import {MessageListData} from "./message_list_data";
import * as message_list_tooltips from "./message_list_tooltips";
import {MessageListView} from "./message_list_view";
import * as narrow_banner from "./narrow_banner";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import {web_mark_read_on_scroll_policy_values} from "./settings_config";
import * as stream_data from "./stream_data";
import {user_settings} from "./user_settings";

export class MessageList {
    // A MessageList is the main interface for a message feed that is
    // rendered in the DOM. Code outside the message feed rendering
    // internals will directly call this module in order to manipulate
    // a message feed.
    //
    // Each MessageList has an associated MessageListData, which
    // manages the messages, and a MessageListView, which manages the
    // the templates/HTML rendering as well as invisible pagination.
    //
    // TODO: The abstraction boundary between this and MessageListView
    // is not particularly well-defined; it could be nice to figure
    // out a good rule.
    constructor(opts) {
        // The MessageListData keeps track of the actual sequence of
        // messages displayed by this MessageList. Most
        // configuration/logic questions in this module will be
        // answered by calling a function from the MessageListData,
        // its Filter, or its FetchStatus object.
        if (opts.data) {
            this.data = opts.data;
        } else {
            const filter = opts.filter;

            this.data = new MessageListData({
                excludes_muted_topics: opts.excludes_muted_topics,
                filter,
            });
        }

        // The table_name is the outer HTML element for this message
        // list in the DOM.
        const table_name = opts.table_name;
        this.table_name = table_name;

        // TODO: This property should likely just be inlined into
        // having the MessageListView code that needs to access it
        // query .data.filter directly.
        const collapse_messages = this.data.filter.supports_collapsing_recipients();

        // The MessageListView object that is responsible for
        // maintaining this message feed's HTML representation in the
        // DOM.
        this.view = new MessageListView(this, table_name, collapse_messages);

        // Whether this is a narrowed message list. The only message
        // list that is not is the home_msg_list global.
        //
        // TODO: It would probably be more readable to replace this
        // with another property with an inverted meaning, since
        // home_msg_list is the message list that is special/unique.
        this.narrowed = this.table_name === "zfilt";

        // TODO: This appears to be unused and can be deleted.
        this.num_appends = 0;

        // Keeps track of whether the user has done a UI interaction,
        // such as "Mark as unread", that should disable marking
        // messages as read until prevent_reading is called again.
        //
        // Distinct from filter.can_mark_messages_read(), which is a
        // property of the type of narrow, regardless of actions by
        // the user. Possibly this can be unified in some nice way.
        this.reading_prevented = false;

        return this;
    }

    prevent_reading() {
        this.reading_prevented = true;
    }

    resume_reading() {
        this.reading_prevented = false;
    }

    add_messages(messages, opts) {
        // This adds all messages to our data, but only returns
        // the currently viewable ones.
        const info = this.data.add_messages(messages);

        const top_messages = info.top_messages;
        const bottom_messages = info.bottom_messages;
        const interior_messages = info.interior_messages;

        // Currently we only need data back from rendering to
        // tell us whether users needs to scroll, which only
        // applies for `append_to_view`, but this may change over
        // time.
        let render_info;

        if (interior_messages.length > 0) {
            this.view.rerender_preserving_scrolltop(true);
            return true;
        }
        if (top_messages.length > 0) {
            this.view.prepend(top_messages);
        }

        if (bottom_messages.length > 0) {
            render_info = this.append_to_view(bottom_messages, opts);
        }

        if (this.narrowed && !this.visibly_empty()) {
            // If adding some new messages to the message tables caused
            // our current narrow to no longer be empty, hide the empty
            // feed placeholder text.
            narrow_banner.hide_empty_narrow_message();
        }

        if (this.narrowed && !this.visibly_empty() && this.selected_id() === -1) {
            // The message list was previously empty, but now isn't
            // due to adding these messages, and we need to select a
            // message. Regardless of whether the messages are new or
            // old, we want to select a message as though we just
            // entered this view.
            this.select_id(this.first_unread_message_id(), {then_scroll: true, use_closest: true});
        }

        return render_info;
    }

    get(id) {
        return this.data.get(id);
    }

    num_items() {
        return this.data.num_items();
    }

    empty() {
        return this.data.empty();
    }

    visibly_empty() {
        return this.data.visibly_empty();
    }

    first() {
        return this.data.first();
    }

    last() {
        return this.data.last();
    }

    ids_greater_or_equal_than(id) {
        return this.data.ids_greater_or_equal_than(id);
    }

    prev() {
        return this.data.prev();
    }

    next() {
        return this.data.next();
    }

    is_at_end() {
        return this.data.is_at_end();
    }

    nth_most_recent_id(n) {
        return this.data.nth_most_recent_id(n);
    }

    is_search() {
        return this.data.is_search();
    }

    can_mark_messages_read() {
        /* Automatically marking messages as read can be disabled for
           three different reasons:
           * The view is structurally a search view, encoded in the
             properties of the message_list_data object.
           * The user recently marked messages in the view as unread, and
             we don't want to lose that state.
           * The user has "Automatically mark messages as read" option
             turned on in their user settings.
        */
        const filter = this.data.filter;
        const is_conversation_view = filter === undefined ? false : filter.is_conversation_view();
        return (
            this.data.can_mark_messages_read() &&
            !this.reading_prevented &&
            !(
                user_settings.web_mark_read_on_scroll_policy ===
                web_mark_read_on_scroll_policy_values.never.code
            ) &&
            !(
                user_settings.web_mark_read_on_scroll_policy ===
                    web_mark_read_on_scroll_policy_values.conversation_only.code &&
                !is_conversation_view
            )
        );
    }

    can_mark_messages_read_without_setting() {
        /*
            Similar to can_mark_messages_read() above, this is a helper
            function to check if messages can be automatically read without
            the "Automatically mark messages as read" setting.
        */
        return this.data.can_mark_messages_read() && !this.reading_prevented;
    }

    clear({clear_selected_id = true} = {}) {
        this.data.clear();
        this.view.clear_rendering_state(true);

        if (clear_selected_id) {
            this.data.clear_selected_id();
        }
    }

    selected_id() {
        return this.data.selected_id();
    }

    select_id(id, opts) {
        opts = {
            then_scroll: false,
            target_scroll_offset: undefined,
            use_closest: false,
            empty_ok: false,
            mark_read: true,
            force_rerender: false,
            ...opts,
            id,
            msg_list: this,
            previously_selected_id: this.data.selected_id(),
        };

        const convert_id = (str_id) => {
            const id = Number.parseFloat(str_id);
            if (Number.isNaN(id)) {
                throw new TypeError("Bad message id " + str_id);
            }
            return id;
        };

        id = convert_id(id);

        const closest_id = this.closest_id(id);

        let error_data;

        // The name "use_closest" option is a bit legacy.  We
        // are always gonna move to the closest visible id; the flag
        // just says whether we call blueslip.error or not.  The caller
        // sets use_closest to true when it expects us to move the
        // pointer as needed, so only generate an error if the flag is
        // false.
        if (!opts.use_closest && closest_id !== id) {
            error_data = {
                table_name: this.table_name,
                id,
                closest_id,
            };
            blueslip.error("Selected message id not in MessageList", error_data);
        }

        if (closest_id === -1 && !opts.empty_ok) {
            error_data = {
                table_name: this.table_name,
                id,
                items_length: this.data.num_items(),
            };
            blueslip.error("Cannot select id -1", error_data);
            throw new Error("Cannot select id -1");
        }

        id = closest_id;
        opts.id = id;
        this.data.set_selected_id(id);

        if (opts.force_rerender) {
            this.rerender();
        } else if (!opts.from_rendering) {
            this.view.maybe_rerender();
        }

        $(document).trigger(new $.Event("message_selected.zulip", opts));
    }

    selected_message() {
        return this.get(this.data.selected_id());
    }

    selected_row() {
        return this.get_row(this.data.selected_id());
    }

    closest_id(id) {
        return this.data.closest_id(id);
    }

    advance_past_messages(msg_ids) {
        return this.data.advance_past_messages(msg_ids);
    }

    selected_idx() {
        return this.data.selected_idx();
    }

    // Maintains a trailing bookend element explaining any changes in
    // your subscribed/unsubscribed status at the bottom of the
    // message list.
    update_trailing_bookend() {
        this.view.clear_trailing_bookend();
        if (!this.narrowed) {
            return;
        }
        const stream_name = narrow_state.stream_name();
        if (stream_name === undefined) {
            return;
        }

        let deactivated = false;
        let just_unsubscribed = false;
        const subscribed = stream_data.is_subscribed_by_name(stream_name);
        const sub = stream_data.get_sub(stream_name);
        const invite_only = sub.invite_only;
        const is_web_public = sub.is_web_public;
        const can_toggle_subscription =
            sub !== undefined && stream_data.can_toggle_subscription(sub);
        if (sub === undefined) {
            deactivated = true;
        } else if (!subscribed && !this.last_message_historical) {
            just_unsubscribed = true;
        }

        this.view.render_trailing_bookend(
            stream_name,
            subscribed,
            deactivated,
            just_unsubscribed,
            can_toggle_subscription,
            page_params.is_spectator,
            invite_only,
            is_web_public,
        );
    }

    unmuted_messages(messages) {
        return this.data.unmuted_messages(messages);
    }

    append(messages, opts) {
        const viewable_messages = this.data.append(messages);
        this.append_to_view(viewable_messages, opts);
    }

    append_to_view(messages, {messages_are_new = false} = {}) {
        this.num_appends += 1;
        const render_info = this.view.append(messages, messages_are_new);
        return render_info;
    }

    remove_and_rerender(message_ids) {
        this.data.remove(message_ids);
        this.rerender();
    }

    show_edit_message($row, edit_obj) {
        if ($row.find(".message_edit_form form").length !== 0) {
            return;
        }
        $row.find(".message_edit_form").append(edit_obj.$form);
        $row.find(".message_content, .status-message, .message_controls").hide();
        $row.find(".sender-status").toggleClass("sender-status-edit");
        $row.find(".messagebox-content").addClass("content_edit_mode");
        $row.find(".message_edit").css("display", "block");
        autosize($row.find(".message_edit_content"));
    }

    hide_edit_message($row) {
        $row.find(".message_content, .status-message, .message_controls").show();
        $row.find(".sender-status").toggleClass("sender-status-edit");
        $row.find(".message_edit_form").empty();
        $row.find(".messagebox-content").removeClass("content_edit_mode");
        $row.find(".message_edit").hide();
        $row.trigger("mouseleave");
    }

    show_edit_topic_on_recipient_row($recipient_row, $form) {
        $recipient_row.find(".topic_edit_form").append($form);
        $recipient_row.find(".on_hover_topic_edit").hide();
        $recipient_row.find(".edit_message_button").hide();
        $recipient_row.find(".stream_topic").hide();
        $recipient_row.find(".topic_edit").show();
        $recipient_row.find(".always_visible_topic_edit").hide();
        $recipient_row.find(".on_hover_topic_resolve").hide();
        $recipient_row.find(".on_hover_topic_unresolve").hide();
        $recipient_row.find(".on_hover_topic_mute").hide();
        $recipient_row.find(".on_hover_topic_unmute").hide();
    }

    hide_edit_topic_on_recipient_row($recipient_row) {
        $recipient_row.find(".stream_topic").show();
        $recipient_row.find(".on_hover_topic_edit").show();
        $recipient_row.find(".edit_message_button").show();
        $recipient_row.find(".topic_edit_form").empty();
        $recipient_row.find(".topic_edit").hide();
        $recipient_row.find(".always_visible_topic_edit").show();
        $recipient_row.find(".on_hover_topic_resolve").show();
        $recipient_row.find(".on_hover_topic_unresolve").show();
        $recipient_row.find(".on_hover_topic_mute").show();
        $recipient_row.find(".on_hover_topic_unmute").show();
    }

    reselect_selected_id() {
        const selected_id = this.data.selected_id();

        if (selected_id !== -1) {
            this.select_id(this.data.selected_id(), {from_rendering: true, mark_read: false});
        }
    }

    rerender_view() {
        this.view.rerender_preserving_scrolltop();
        this.reselect_selected_id();
    }

    rerender() {
        // We need to destroy all the tippy instances from the DOM before re-rendering to
        // prevent the appearance of tooltips whose reference has been removed.
        message_list_tooltips.destroy_all_message_list_tooltips();
        // We need to clear the rendering state, rather than just
        // doing clear_table, since we want to potentially recollapse
        // things.
        this.data.reset_select_to_closest();
        this.view.clear_rendering_state(false);
        this.view.update_render_window(this.selected_idx(), false);

        if (this.narrowed) {
            if (
                this.visibly_empty() &&
                this.data.fetch_status.has_found_oldest() &&
                this.data.fetch_status.has_found_newest()
            ) {
                // Show the empty narrow message only if we're certain
                // that the view doesn't have messages that we're
                // waiting for the server to send us.
                narrow_banner.show_empty_narrow_message();
            } else {
                narrow_banner.hide_empty_narrow_message();
            }
        }
        this.rerender_view();
    }

    update_muting_and_rerender() {
        // For the home message list, we need to re-initialize
        // _all_items for stream muting/topic unmuting from
        // all_messages_data, since otherwise unmuting a previously
        // muted stream won't work.
        //
        // TODO: The zhome conditional is a bit awkward, but a check
        // for whether the filter excludes muted streams wouldn't be
        // correct, because other narrows can't pull from
        // all_messages.
        if (this.table_name === "zhome") {
            this.data.clear();
            this.data.add_messages(all_messages_data.all_messages());
        }

        this.data.update_items_for_muting();
        // We need to rerender whether or not the narrow hides muted
        // topics, because we need to update recipient bars for topics
        // we've muted when we are displaying those topics.
        //
        // We could avoid a rerender if we can provide that this
        // narrow cannot have contained messages to muted topics
        // either before or after the state change.  The right place
        // to do this is in the message_events.js code path for
        // processing topic edits, since that's the only place we'll
        // call this frequently anyway.
        //
        // But in any case, we need to rerender the list for user muting,
        // to make sure only the right messages are hidden.
        this.rerender();
    }

    all_messages() {
        return this.data.all_messages();
    }

    first_unread_message_id() {
        return this.data.first_unread_message_id();
    }

    has_unread_messages() {
        return this.data.has_unread_messages();
    }

    message_range(start, end) {
        return this.data.message_range(start, end);
    }

    get_row(id) {
        return this.view.get_row(id);
    }

    change_message_id(old_id, new_id) {
        const require_rerender = this.data.change_message_id(old_id, new_id);
        if (require_rerender) {
            this.rerender_view();
        }
    }

    get_last_message_sent_by_me() {
        return this.data.get_last_message_sent_by_me();
    }
}
