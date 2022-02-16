import autosize from "autosize";
import $ from "jquery";

import * as blueslip from "./blueslip";
import {MessageListData} from "./message_list_data";
import {MessageListView} from "./message_list_view";
import * as narrow_banner from "./narrow_banner";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";

export let narrowed;

export function set_narrowed(value) {
    narrowed = value;
}

export class MessageList {
    constructor(opts) {
        if (opts.data) {
            this.data = opts.data;
        } else {
            const filter = opts.filter;

            this.data = new MessageListData({
                excludes_muted_topics: opts.excludes_muted_topics,
                filter,
            });
        }

        const collapse_messages = this.data.filter.supports_collapsing_recipients();
        const table_name = opts.table_name;
        this.view = new MessageListView(this, table_name, collapse_messages);
        this.table_name = table_name;
        this.narrowed = this.table_name === "zfilt";
        this.num_appends = 0;

        return this;
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

        if (this === narrowed && !this.empty()) {
            // If adding some new messages to the message tables caused
            // our current narrow to no longer be empty, hide the empty
            // feed placeholder text.
            narrow_banner.hide_empty_narrow_message();
        }

        if (this === narrowed && !this.empty() && this.selected_id() === -1) {
            // And also select the newly arrived message.
            this.select_id(this.selected_id(), {then_scroll: true, use_closest: true});
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

    first() {
        return this.data.first();
    }

    last() {
        return this.data.last();
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
        return this.data.can_mark_messages_read();
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

    reselect_selected_id() {
        this.select_id(this.data.selected_id(), {from_rendering: true});
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
        const stream_name = narrow_state.stream();
        if (stream_name === undefined) {
            return;
        }

        let deactivated = false;
        let just_unsubscribed = false;
        const subscribed = stream_data.is_subscribed_by_name(stream_name);
        const sub = stream_data.get_sub(stream_name);
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

    show_edit_message(row, edit_obj) {
        if (row.find(".message_edit_form form").length !== 0) {
            return;
        }
        row.find(".message_edit_form").append(edit_obj.form);
        row.find(".message_content, .status-message, .message_controls").hide();
        row.find(".message_edit").css("display", "block");
        autosize(row.find(".message_edit_content"));
    }

    hide_edit_message(row) {
        row.find(".message_content, .status-message, .message_controls").show();
        row.find(".message_edit_form").empty();
        row.find(".message_edit").hide();
        row.trigger("mouseleave");
    }

    show_edit_topic_on_recipient_row(recipient_row, form) {
        recipient_row.find(".topic_edit_form").append(form);
        recipient_row.find(".on_hover_topic_edit").hide();
        recipient_row.find(".edit_content_button").hide();
        recipient_row.find(".stream_topic").hide();
        recipient_row.find(".topic_edit").show();
        recipient_row.find(".always_visible_topic_edit").hide();
    }

    hide_edit_topic_on_recipient_row(recipient_row) {
        recipient_row.find(".stream_topic").show();
        recipient_row.find(".on_hover_topic_edit").show();
        recipient_row.find(".edit_content_button").show();
        recipient_row.find(".topic_edit_form").empty();
        recipient_row.find(".topic_edit").hide();
        recipient_row.find(".always_visible_topic_edit").show();
    }

    show_message_as_read(message, options) {
        const row = this.get_row(message.id);
        if (options.from === "pointer" || options.from === "server") {
            row.find(".unread_marker").addClass("fast_fade");
        } else {
            row.find(".unread_marker").addClass("slow_fade");
        }
        row.removeClass("unread");
    }

    rerender_view() {
        this.view.rerender_preserving_scrolltop();
        this.redo_selection();
    }

    rerender() {
        // We need to clear the rendering state, rather than just
        // doing clear_table, since we want to potentially recollapse
        // things.
        this.data.reset_select_to_closest();
        this.view.clear_rendering_state(false);
        this.view.update_render_window(this.selected_idx(), false);

        if (this === narrowed) {
            if (this.empty()) {
                narrow_banner.show_empty_narrow_message();
            } else {
                narrow_banner.hide_empty_narrow_message();
            }
        }
        this.rerender_view();
    }

    redo_selection() {
        const selected_id = this.data.selected_id();

        if (selected_id !== -1) {
            this.select_id(selected_id);
        }
    }

    update_muting_and_rerender() {
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
