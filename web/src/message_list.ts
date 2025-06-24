import autosize from "autosize";
import $ from "jquery";
import assert from "minimalistic-assert";

import * as activity_ui from "./activity_ui.ts";
import * as blueslip from "./blueslip.ts";
import * as compose_tooltips from "./compose_tooltips.ts";
import * as compose_ui from "./compose_ui.ts";
import type {MessageListData} from "./message_list_data.ts";
import * as message_list_tooltips from "./message_list_tooltips.ts";
import {MessageListView} from "./message_list_view.ts";
import type {Message} from "./message_store.ts";
import * as narrow_banner from "./narrow_banner.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import {web_mark_read_on_scroll_policy_values} from "./settings_config.ts";
import * as stream_data from "./stream_data.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";

export type RenderInfo = {need_user_to_scroll: boolean};

export type SelectIdOpts = {
    then_scroll?: boolean;
    target_scroll_offset?: number;
    use_closest?: boolean;
    empty_ok?: boolean;
    mark_read?: boolean;
    force_rerender?: boolean;
    from_scroll?: boolean;
    from_rendering?: boolean;
};

export type MessageSelectedEventOpts = {
    then_scroll: boolean;
    target_scroll_offset: number | undefined;
    use_closest: boolean;
    empty_ok: boolean;
    mark_read: boolean;
    force_rerender: boolean;
    from_scroll?: boolean;
    from_rendering?: boolean;
    id: number;
    msg_list: MessageList;
    previously_selected_id: number;
};

export type MessageSelectedEvent<TDelegateTarget, TData, TCurrentTarget, TTarget> =
    JQuery.EventBase<TDelegateTarget, TData, TCurrentTarget, TTarget> & {
        type: "message_selected.zulip";
    } & MessageSelectedEventOpts;

declare global {
    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace JQuery {
        // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
        interface TypeToTriggeredEventMap<TDelegateTarget, TData, TCurrentTarget, TTarget> {
            ["message_selected.zulip"]: MessageSelectedEvent<
                TDelegateTarget,
                TData,
                TCurrentTarget,
                TTarget
            >;
        }
    }
}

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
export class MessageList {
    static id_counter = 0;

    id: number;
    // The MessageListData keeps track of the actual sequence of
    // messages displayed by this MessageList. Most
    // configuration/logic questions in this module will be
    // answered by calling a function from the MessageListData,
    // its Filter, or its FetchStatus object.
    data: MessageListData;
    // The MessageListView object that is responsible for
    // maintaining this message feed's HTML representation in the
    // DOM.
    view: MessageListView;
    // If this message list is for the combined feed view.
    is_combined_feed_view: boolean;
    // Keeps track of whether the user has done a UI interaction,
    // such as "Mark as unread", that should disable marking
    // messages as read until prevent_reading is called again.
    //
    // Distinct from filter.can_mark_messages_read(), which is a
    // property of the type of narrow, regardless of actions by
    // the user. Possibly this can be unified in some nice way.
    reading_prevented: boolean;

    // TODO: Clean up these monkey-patched properties somehow.
    last_message_historical?: boolean;
    should_trigger_message_selected_event?: boolean;

    constructor(opts: {
        data: MessageListData;
        excludes_muted_topics?: boolean;
        is_node_test?: boolean;
    }) {
        MessageList.id_counter += 1;
        this.id = MessageList.id_counter;
        this.data = opts.data;
        this.data.set_rendered_message_list_id(this.id);

        // TODO: This property should likely just be inlined into
        // having the MessageListView code that needs to access it
        // query .data.filter directly.
        const collapse_messages = this.data.filter.contains_no_partial_conversations();

        this.view = new MessageListView(this, collapse_messages, opts.is_node_test);
        this.is_combined_feed_view = this.data.filter.is_in_home();
        this.reading_prevented = false;

        return this;
    }

    should_preserve_current_rendered_state(): boolean {
        // Whether this message list is preserved in the DOM even
        // when viewing other views -- a valuable optimization for
        // fast toggling between the combined feed and other views,
        // which we enable only when that is the user's home view.
        //
        // This is intentionally not live-updated when web_home_view
        // changes, since it's easier to reason about if this
        // optimization is active or not for an entire session.
        if (user_settings.web_home_view !== "all_messages" || !this.is_combined_feed_view) {
            return false;
        }

        // If we click on a narrow, we go the first unread message.
        // If first unread message is not available in a cached message list,
        // we render by selecting the `message_list.last()` message.
        // This is incorrect unless we have found the newest message.
        //
        // So, we don't preserve the rendered state of this list if first unread message
        // is not available to us. Otherwise, this leads to confusion when we are
        // restoring the rendered list but our first unread message is not available
        // and fetching it from the server could lead to non-contiguous messages history.
        //
        // NOTE: Non-contiguous message history can still happen in the opposite situation
        // where user is narrowing to a message id which is not present in the rendered list.
        // In this case, we create a new list and if the new fetched history contains first
        // unread message, we preserve this list and discard others with the same filter.
        //
        // This nicely supports the common workflow of user reloading with a `then_select_id`
        // and then scrolling to the first unread message; then narrowing to the unread topic
        // and combing back to combined feed. The combined feed will be rendered in this case
        // but not if we decided to discard this list based on if anchor was on `first_unread.
        //
        // Since we know we are checking for first unread unmuted message in combined feed,
        // we can use `unread.first_unread_unmuted_message_id` to correctly check if we have
        // fetched the first unread message.
        //
        // TODO: For supporting other narrows, we need to check if we have fetched the first
        // unread message for that narrow, for which we will have to query server for the
        // first unread message id. Maybe that can be part of the narrow fetch query itself.
        const first_unread_message = this.get(unread.first_unread_unmuted_message_id);
        if (!first_unread_message?.unread) {
            // If we have found the newest message, we can preserve the rendered state.
            return this.data.fetch_status.has_found_newest();
        }

        // If we have found the first unread message, we can preserve the rendered state.
        return true;
    }

    is_current_message_list(): boolean {
        return this.view.is_current_message_list();
    }

    prevent_reading(): void {
        this.reading_prevented = true;
    }

    resume_reading(): void {
        this.reading_prevented = false;
    }

    add_messages(
        messages: Message[],
        append_to_view_opts: {messages_are_new?: boolean} = {},
        is_contiguous_history = false,
    ): RenderInfo | undefined {
        // This adds all messages to our data, but only returns
        // the currently viewable ones.
        const info = this.data.add_messages(messages, is_contiguous_history);

        const top_messages = info.top_messages;
        const bottom_messages = info.bottom_messages;
        const interior_messages = info.interior_messages;

        if (top_messages.length + interior_messages.length + bottom_messages.length === 0) {
            // This add messages call had no effect on the message list.
            return undefined;
        }

        // Currently we only need data back from rendering to
        // tell us whether users needs to scroll, which only
        // applies for `append_to_view`, but this may change over
        // time.
        let render_info;

        if (interior_messages.length > 0) {
            this.view.rerender_preserving_scrolltop(true);
            this.update_user_sidebar_participants();
            return {need_user_to_scroll: true};
        }
        if (top_messages.length > 0) {
            this.view.prepend(top_messages);
        }

        if (bottom_messages.length > 0) {
            render_info = this.append_to_view(bottom_messages, append_to_view_opts);
        }

        if (!this.visibly_empty() && this.is_current_message_list()) {
            // If adding some new messages to the message tables caused
            // our current narrow to no longer be empty, hide the empty
            // feed placeholder text.
            narrow_banner.hide_empty_narrow_message();
        }

        if (!this.visibly_empty() && this.selected_id() === -1 && this.is_current_message_list()) {
            // The message list was previously empty, but now isn't
            // due to adding these messages, and we need to select a
            // message. Regardless of whether the messages are new or
            // old, we want to select a message as though we just
            // entered this view.
            const first_unread_message_id = this.first_unread_message_id();
            assert(first_unread_message_id !== undefined);
            this.select_id(first_unread_message_id, {then_scroll: true, use_closest: true});
        }

        this.update_user_sidebar_participants();
        return render_info;
    }

    get(id: number): Message | undefined {
        return this.data.get(id);
    }

    msg_id_in_fetched_range(msg_id: number): boolean {
        return this.data.msg_id_in_fetched_range(msg_id);
    }

    num_items(): number {
        return this.data.num_items();
    }

    empty(): boolean {
        return this.data.empty();
    }

    visibly_empty(): boolean {
        return this.data.visibly_empty();
    }

    first(): Message | undefined {
        return this.data.first();
    }

    last(): Message | undefined {
        return this.data.last();
    }

    prev(): number | undefined {
        return this.data.prev();
    }

    next(): number | undefined {
        return this.data.next();
    }

    is_at_end(): boolean {
        return this.data.is_at_end();
    }

    is_keyword_search(): boolean {
        return this.data.is_keyword_search();
    }

    can_mark_messages_read(): boolean {
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

    can_mark_messages_read_without_setting(): boolean {
        /*
            Similar to can_mark_messages_read() above, this is a helper
            function to check if messages can be automatically read without
            the "Automatically mark messages as read" setting.
        */
        return this.data.can_mark_messages_read() && !this.reading_prevented;
    }

    clear({clear_selected_id = true} = {}): void {
        this.data.clear();
        this.view.clear_rendering_state(true);

        if (clear_selected_id) {
            this.data.clear_selected_id();
        }
    }

    selected_id(): number {
        return this.data.selected_id();
    }

    select_id(id: number | string, select_id_opts?: SelectIdOpts): void {
        if (typeof id === "string") {
            blueslip.warn("Call to select_id with string id");
            id = Number.parseFloat(id);
            if (Number.isNaN(id)) {
                throw new TypeError("Bad message id " + id);
            }
        }
        const opts: MessageSelectedEventOpts = {
            then_scroll: false,
            target_scroll_offset: undefined,
            use_closest: false,
            empty_ok: false,
            mark_read: true,
            force_rerender: false,
            ...select_id_opts,
            id,
            msg_list: this,
            previously_selected_id: this.data.selected_id(),
        };

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
                filter_terms: this.data.filter.terms(),
                id,
                closest_id,
            };
            blueslip.error("Selected message id not in MessageList", error_data);
        }

        if (closest_id === -1 && !opts.empty_ok) {
            error_data = {
                filter_terms: this.data.filter.terms(),
                id,
                items_length: this.data.num_items(),
            };
            blueslip.error("Cannot select id -1", error_data);
            throw new Error("Cannot select id -1");
        }

        id = closest_id;
        opts.id = id;
        this.data.set_selected_id(id);

        // Avoid recursive calls to message_selected event
        // by temporarily blocking triggering the event by
        // setting `should_trigger_message_selected_event`.
        if (opts.force_rerender) {
            this.should_trigger_message_selected_event = false;
            this.rerender();
            this.should_trigger_message_selected_event = true;
        } else if (!opts.from_rendering) {
            this.should_trigger_message_selected_event = false;
            this.view.maybe_rerender();
            this.should_trigger_message_selected_event = true;
        }

        if (this.should_trigger_message_selected_event) {
            $(document).trigger(new $.Event("message_selected.zulip", opts));
        }
    }

    selected_message(): Message | undefined {
        return this.get(this.data.selected_id());
    }

    selected_row(): JQuery {
        return this.get_row(this.data.selected_id());
    }

    closest_id(id: number): number {
        return this.data.closest_id(id);
    }

    advance_past_messages(msg_ids: number[]): void {
        this.data.advance_past_messages(msg_ids);
    }

    selected_idx(): number {
        return this.data.selected_idx();
    }

    // Maintains a trailing bookend element explaining any changes in
    // your subscribed/unsubscribed status at the bottom of the
    // message list.
    update_trailing_bookend(force_render = false): void {
        this.view.clear_trailing_bookend();
        if (this.is_combined_feed_view) {
            return;
        }

        const stream_id = narrow_state.stream_id();
        if (stream_id === undefined) {
            // Trailing bookends are only for channel views.
            return;
        }

        // If user narrows to a stream, don't update
        // trailing bookend if user is subscribed.
        const sub = stream_data.get_sub_by_id(stream_id);
        if (
            sub &&
            sub.subscribed &&
            !this.last_message_historical &&
            !page_params.is_spectator &&
            !force_render
        ) {
            return;
        }

        let deactivated = false;
        let just_unsubscribed = false;
        const subscribed = stream_data.is_subscribed(stream_id);
        const invite_only = sub?.invite_only;
        const is_web_public = sub?.is_web_public;
        if (sub === undefined || sub.is_archived) {
            deactivated = true;
        } else if (!subscribed && !this.last_message_historical && !this.empty()) {
            just_unsubscribed = true;
        }

        this.view.render_trailing_bookend(
            stream_id,
            sub?.name,
            subscribed,
            deactivated,
            just_unsubscribed,
            page_params.is_spectator,
            invite_only ?? false,
            is_web_public ?? false,
        );
    }

    unmuted_messages(messages: Message[]): Message[] {
        return this.data.unmuted_messages(messages);
    }

    append(messages: Message[], opts: {messages_are_new: boolean}): void {
        const viewable_messages = this.data.append(messages);
        this.append_to_view(viewable_messages, opts);
    }

    append_to_view(messages: Message[], {messages_are_new = false} = {}): RenderInfo | undefined {
        return this.view.append(messages, messages_are_new);
    }

    remove_and_rerender(message_ids: number[]): void {
        const should_rerender = this.data.remove(message_ids);
        this.update_user_sidebar_participants();
        if (!should_rerender) {
            return;
        }
        this.rerender();
    }

    update_user_sidebar_participants(): void {
        if (this.is_current_message_list()) {
            activity_ui.rerender_user_sidebar_participants();
        }
    }

    show_edit_message($row: JQuery, $form: JQuery): void {
        if ($row.find(".message_edit_form form").length > 0) {
            return;
        }
        $row.find(".messagebox-content").append($form);
        $row.find(".message_content, .status-message, .message_controls").hide();
        $row.find(".messagebox-content").addClass("content_edit_mode");
        // autosize will not change the height of the textarea if the `$row` is not
        // rendered in DOM yet. So, we call `autosize.update` post render.
        autosize($row.find(".message_edit_content"));
        compose_ui.maybe_show_scrolling_formatting_buttons(".message-edit-feature-group");
    }

    hide_edit_message($row: JQuery): void {
        if ($row.find(".message_edit_form form").length === 0) {
            return;
        }
        compose_tooltips.hide_compose_control_button_tooltips($row);
        $row.find(".message_content, .status-message, .message_controls").show();
        $row.find(".messagebox-content").removeClass("content_edit_mode");
        $row.find(".message_edit").remove();
        $row.trigger("mouseleave");
    }

    show_edit_topic_on_recipient_row($recipient_row: JQuery, $form: JQuery): void {
        $recipient_row.find(".topic_edit").append($form);
        $recipient_row.find(".stream_topic").hide();
        $recipient_row.find(".topic_edit").show();
        $recipient_row.find(".recipient-bar-control").hide();
    }

    hide_edit_topic_on_recipient_row($recipient_row: JQuery): void {
        $recipient_row.find(".stream_topic").show();
        $recipient_row.find(".topic_edit").empty();
        $recipient_row.find(".topic_edit").hide();
        $recipient_row.find(".recipient-bar-control").show();
    }

    reselect_selected_id(): void {
        const selected_id = this.data.selected_id();

        if (selected_id !== -1) {
            this.select_id(this.data.selected_id(), {from_rendering: true, mark_read: false});
        }
    }

    rerender_view(): void {
        this.view.rerender_preserving_scrolltop();
        this.reselect_selected_id();
    }

    rerender(): void {
        // We need to destroy all the tippy instances from the DOM before re-rendering to
        // prevent the appearance of tooltips whose reference has been removed.
        message_list_tooltips.destroy_all_message_list_tooltips();
        // We need to clear the rendering state, rather than just
        // doing clear_table, since we want to potentially recollapse
        // things.
        this.data.reset_select_to_closest();
        this.view.clear_rendering_state(false);
        this.view.update_render_window(this.selected_idx(), false);

        if (
            this.visibly_empty() &&
            this.data.fetch_status.has_found_oldest() &&
            this.data.fetch_status.has_found_newest()
        ) {
            // Show the empty narrow message only if we're certain
            // that the view doesn't have messages that we're
            // waiting for the server to send us.
            narrow_banner.show_empty_narrow_message(this.data.filter);
        } else {
            narrow_banner.hide_empty_narrow_message();
        }
        this.rerender_view();
    }

    update_muting_and_rerender(): void {
        this.data.update_items_for_muting();
        // We need to rerender whether or not the narrow hides muted
        // topics, because we need to update recipient bars for topics
        // we've muted when we are displaying those topics.
        //
        // We could avoid a rerender if we can provide that this
        // narrow cannot have contained messages to muted topics
        // either before or after the state change.  The right place
        // to do this is in the message_events.ts code path for
        // processing topic edits, since that's the only place we'll
        // call this frequently anyway.
        //
        // But in any case, we need to rerender the list for user muting,
        // to make sure only the right messages are hidden.
        this.rerender();

        // While this can have changed the conversation's visible
        // participants, we don't need to call
        // this.update_user_sidebar_participants, because changing a
        // muted user's state already does a full sidebar redraw.
    }

    all_messages(): Message[] {
        return this.data.all_messages();
    }

    first_unread_message_id(): number | undefined {
        return this.data.first_unread_message_id();
    }

    has_unread_messages(): boolean {
        return this.data.has_unread_messages();
    }

    message_range(start: number, end: number): Message[] {
        return this.data.message_range(start, end);
    }

    get_row(id: number): JQuery {
        return this.view.get_row(id);
    }

    change_message_id(old_id: number, new_id: number): void {
        const require_rerender = this.data.change_message_id(old_id, new_id);
        if (require_rerender) {
            this.rerender_view();
        }
    }

    get_last_message_sent_by_me(): Message | undefined {
        return this.data.get_last_message_sent_by_me();
    }
}
