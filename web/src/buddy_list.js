import $ from "jquery";

import render_empty_list_widget_for_list from "../templates/empty_list_widget_for_list.hbs";
import render_presence_row from "../templates/presence_row.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import {$t} from "./i18n";
import * as message_viewport from "./message_viewport";
import * as narrow_state from "./narrow_state";
import * as padded_widget from "./padded_widget";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as scroll_util from "./scroll_util";

class BuddyListConf {
    matching_view_list_selector = "#buddy-list-users-matching-view";
    other_user_list_selector = "#buddy-list-other-users";
    scroll_container_selector = "#buddy_list_wrapper";
    item_selector = "li.user_sidebar_entry";
    padding_selector = "#buddy_list_wrapper_padding";

    items_to_html(opts) {
        const html = render_presence_rows({presence_rows: opts.items});
        return html;
    }

    item_to_html(opts) {
        const html = render_presence_row(opts.item);
        return html;
    }

    get_li_from_user_id(opts) {
        const user_id = opts.user_id;
        const $users_matching_view_container = $(this.matching_view_list_selector);
        const $li = $users_matching_view_container.find(
            `${this.item_selector}[data-user-id='${CSS.escape(user_id)}']`,
        );
        if ($li.length > 0) {
            return $li;
        }

        const $other_users_container = $(this.other_user_list_selector);
        return $other_users_container.find(
            `${this.item_selector}[data-user-id='${CSS.escape(user_id)}']`,
        );
    }

    get_user_id_from_li(opts) {
        return Number.parseInt(opts.$li.expectOne().attr("data-user-id"), 10);
    }

    get_data_from_user_ids(user_ids) {
        const data = buddy_data.get_items_for_users(user_ids);
        return data;
    }

    compare_function = buddy_data.compare_function;

    height_to_fill() {
        // Because the buddy list gets sized dynamically, we err on the side
        // of using the height of the entire viewport for deciding
        // how much content to render.  Even on tall monitors this should
        // still be a significant optimization for orgs with thousands of
        // users.
        const height = message_viewport.height();
        return height;
    }
}

export class BuddyList extends BuddyListConf {
    all_user_ids = [];
    users_matching_view_ids = [];
    other_user_ids = [];

    populate(opts) {
        this.render_count = 0;
        this.$users_matching_view_container.empty();
        this.users_matching_view_ids = [];
        this.$other_users_container.empty();
        this.other_user_ids = [];

        // We rely on our caller to give us items
        // in already-sorted order.
        this.all_user_ids = opts.all_user_ids;

        this.fill_screen_with_content();

        // We do a handful of things once we're done rendering all the users,
        // and each of these tasks need shared data that we'll compute first.
        // (More to come in upcoming commits.)
        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();

        // If we have only "other users" and aren't in a stream/DM view
        // then we don't show section headers and only show one untitled
        // section.
        const hide_headers = this.should_hide_headers(current_sub, pm_ids_set);
        const subscriber_count = this.total_subscriber_count(current_sub, pm_ids_set);
        const total_user_count = people.get_active_human_count();
        const other_users_count = total_user_count - subscriber_count;
        const has_inactive_users_matching_view =
            subscriber_count > this.users_matching_view_ids.length;
        const has_inactive_other_users = other_users_count > this.other_user_ids.length;

        const data = {
            has_inactive_users_matching_view,
            has_inactive_other_users,
        };

        if (!hide_headers) {
            this.update_empty_list_placeholders(data);
        }
    }

    update_empty_list_placeholders({has_inactive_users_matching_narrow, has_inactive_other_users}) {
        let empty_list_message;
        const is_searching_users = buddy_data.get_is_searching_users();
        if (is_searching_users) {
            empty_list_message = $t({defaultMessage: "No matching users."});
        } else if (has_inactive_other_users) {
            empty_list_message = $t({defaultMessage: "No active users."});
        } else {
            empty_list_message = $t({defaultMessage: "None."});
        }

        $("#buddy-list-other-users").data("search-results-empty", empty_list_message);
        if ($("#buddy-list-other-users .empty-list-message").length) {
            const empty_list_widget = render_empty_list_widget_for_list({empty_list_message});
            $("#buddy-list-other-users").empty();
            $("#buddy-list-other-users").append(empty_list_widget);
        }

        if (!is_searching_users) {
            if (has_inactive_users_matching_narrow) {
                empty_list_message = $t({defaultMessage: "No active users."});
            } else {
                empty_list_message = $t({defaultMessage: "None."});
            }
        }

        $("#buddy-list-users-matching-view").data("search-results-empty", empty_list_message);
        if ($("#buddy-list-users-matching-view .empty-list-message").length) {
            const empty_list_widget = render_empty_list_widget_for_list({empty_list_message});
            $("#buddy-list-users-matching-view").empty();
            $("#buddy-list-users-matching-view").append(empty_list_widget);
        }
    }

    render_more(opts) {
        const chunk_size = opts.chunk_size;

        const begin = this.render_count;
        const end = begin + chunk_size;

        const more_user_ids = this.all_user_ids.slice(begin, end);

        if (more_user_ids.length === 0) {
            return;
        }

        const items = this.get_data_from_user_ids(more_user_ids);
        const subscribed_users = [];
        const other_users = [];
        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();

        for (const item of items) {
            if (buddy_data.user_matches_narrow(item.user_id, pm_ids_set, current_sub?.stream_id)) {
                subscribed_users.push(item);
                this.users_matching_view_ids.push(item.user_id);
            } else {
                other_users.push(item);
                this.other_user_ids.push(item.user_id);
            }
        }

        // Remove the empty list message before adding users
        if (
            $(`${this.matching_view_list_selector} .empty-list-message`).length > 0 &&
            subscribed_users.length
        ) {
            this.$users_matching_view_container.empty();
        }
        const subscribed_users_html = this.items_to_html({
            items: subscribed_users,
        });
        this.$users_matching_view_container = $(this.matching_view_list_selector);
        this.$users_matching_view_container.append(subscribed_users_html);

        // Remove the empty list message before adding users
        if (
            $(`${this.other_user_list_selector} .empty-list-message`).length > 0 &&
            other_users.length
        ) {
            this.$other_users_container.empty();
        }
        const other_users_html = this.items_to_html({
            items: other_users,
        });
        this.$other_users_container = $(this.other_user_list_selector);
        this.$other_users_container.append(other_users_html);

        const hide_headers = this.should_hide_headers(current_sub, pm_ids_set);
        $("#buddy-list-users-matching-view-container").toggleClass("no-display", hide_headers);
        $("#buddy-list-other-users-container .buddy-list-subsection-header").toggleClass(
            "no-display",
            hide_headers,
        );

        // Invariant: more_user_ids.length >= items.length.
        // (Usually they're the same, but occasionally user ids
        // won't return valid items.  Even though we don't
        // actually render these user ids, we still "count" them
        // as rendered.

        this.render_count += more_user_ids.length;
        this.update_padding();
    }

    should_hide_headers(current_sub, pm_ids_set) {
        // If we have only "other users" and aren't in a stream/DM view
        // then we don't show section headers and only show one untitled
        // section.
        return this.users_matching_view_ids.length === 0 && !current_sub && !pm_ids_set.size;
    }

    total_subscriber_count(current_sub, pm_ids_set) {
        // Includes inactive users who might not show up in the buddy list.
        if (current_sub) {
            return peer_data.get_subscriber_count(current_sub.stream_id, false);
        } else if (pm_ids_set.size) {
            const pm_ids_list = [...pm_ids_set];
            // Plus one for the "me" user, who isn't in the recipients list (except
            // for when it's a private message conversation with only "me" in it).
            if (pm_ids_list.length === 1 && people.is_my_user_id(pm_ids_list[0])) {
                return 1;
            }
            return pm_ids_list.length + 1;
        }
        return 0;
    }

    get_items() {
        const $user_matching_view_obj = this.$users_matching_view_container.find(
            `${this.item_selector}`,
        );
        const $users_matching_view_elems = $user_matching_view_obj.map((_i, elem) => $(elem));

        const $other_user_obj = this.$other_users_container.find(`${this.item_selector}`);
        const $other_user_elems = $other_user_obj.map((_i, elem) => $(elem));

        return [...$users_matching_view_elems, ...$other_user_elems];
    }

    // From `type List<Key>`, where the key is a user_id.
    first_key() {
        if (this.users_matching_view_ids.length) {
            return this.users_matching_view_ids[0];
        }
        if (this.other_user_ids.length) {
            return this.other_user_ids[0];
        }
        return undefined;
    }

    // From `type List<Key>`, where the key is a user_id.
    prev_key(key) {
        let i = this.users_matching_view_ids.indexOf(key);
        // This would be the middle of the list of users matching view,
        // moving to a prev user matching the view.
        if (i > 0) {
            return this.users_matching_view_ids[i - 1];
        }
        // If it's the first user matching the view, we don't move the selection.
        if (i === 0) {
            return undefined;
        }

        // This would be the middle of the other users list moving to a prev other user.
        i = this.other_user_ids.indexOf(key);
        if (i > 0) {
            return this.other_user_ids[i - 1];
        }
        // The key before the first other user is the last user matching view, if that exists,
        // and if it doesn't then we don't move the selection.
        if (i === 0) {
            if (this.users_matching_view_ids.length > 0) {
                return this.users_matching_view_ids.at(-1);
            }
            return undefined;
        }
        // The only way we reach here is if the key isn't found in either list,
        // which shouldn't happen.
        blueslip.error("Couldn't find key in buddy list", {
            key,
            users_matching_view_ids: this.users_matching_view_ids,
            other_user_ids: this.other_user_ids,
        });
        return undefined;
    }

    // From `type List<Key>`, where the key is a user_id.
    next_key(key) {
        let i = this.users_matching_view_ids.indexOf(key);
        // Moving from users matching the view to the list of other users,
        // if they exist, otherwise do nothing.
        if (i >= 0 && i === this.users_matching_view_ids.length - 1) {
            if (this.other_user_ids.length > 0) {
                return this.other_user_ids[0];
            }
            return undefined;
        }
        // This is a regular move within the list of users matching the view.
        if (i >= 0) {
            return this.users_matching_view_ids[i + 1];
        }

        i = this.other_user_ids.indexOf(key);
        // If we're at the end of other users, we don't do anything.
        if (i >= 0 && i === this.other_user_ids.length - 1) {
            return undefined;
        }
        // This is a regular move within other users.
        if (i >= 0) {
            return this.other_user_ids[i + 1];
        }

        // The only way we reach here is if the key isn't found in either list,
        // which shouldn't happen.
        blueslip.error("Couldn't find key in buddy list", {
            key,
            users_matching_view_ids: this.users_matching_view_ids,
            other_user_ids: this.other_user_ids,
        });
        return undefined;
    }

    maybe_remove_user_id(opts) {
        let pos = this.users_matching_view_ids.indexOf(opts.user_id);
        if (pos >= 0) {
            this.users_matching_view_ids.splice(pos, 1);
        } else {
            pos = this.other_user_ids.indexOf(opts.user_id);
            if (pos < 0) {
                return;
            }
            this.other_user_ids.splice(pos, 1);
        }
        pos = this.all_user_ids.indexOf(opts.user_id);
        this.all_user_ids.splice(pos, 1);

        if (pos < this.render_count) {
            this.render_count -= 1;
            const $li = this.find_li({key: opts.user_id});
            $li.remove();
            this.update_padding();
        }
    }

    find_position(opts) {
        const user_id = opts.user_id;
        let i;

        const user_id_list = opts.user_id_list;

        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();

        for (i = 0; i < user_id_list.length; i += 1) {
            const list_user_id = user_id_list[i];

            if (this.compare_function(user_id, list_user_id, current_sub, pm_ids_set) < 0) {
                return i;
            }
        }

        return user_id_list.length;
    }

    force_render(opts) {
        const pos = opts.pos;

        // Try to render a bit optimistically here.
        const cushion_size = 3;
        const chunk_size = pos + cushion_size - this.render_count;

        if (chunk_size <= 0) {
            blueslip.error("cannot show user id at this position", {
                pos,
                render_count: this.render_count,
                chunk_size,
            });
        }

        this.render_more({
            chunk_size,
        });
    }

    find_li(opts) {
        const user_id = opts.key;

        // Try direct DOM lookup first for speed.
        let $li = this.get_li_from_user_id({
            user_id,
        });

        if ($li.length === 1) {
            return $li;
        }

        if (!opts.force_render) {
            // Most callers don't force us to render a list
            // item that wouldn't be on-screen anyway.
            return $li;
        }

        // We reference all_user_ids to see if we've rendered
        // it yet.
        const pos = this.all_user_ids.indexOf(user_id);

        if (pos < 0) {
            // TODO: See ListCursor.get_row() for why this is
            //       a bit janky now.
            return [];
        }

        this.force_render({
            pos,
        });

        $li = this.get_li_from_user_id({
            user_id,
        });

        return $li;
    }

    insert_new_html(opts) {
        const user_id_following_insertion = opts.new_user_id;
        const html = opts.html;
        const new_pos_in_all_users = opts.new_pos_in_all_users;
        const is_subscribed_user = opts.is_subscribed_user;

        // This means we're inserting at the end
        if (user_id_following_insertion === undefined) {
            if (new_pos_in_all_users === this.render_count) {
                this.render_count += 1;
                if (is_subscribed_user) {
                    this.$users_matching_view_container.append(html);
                } else {
                    this.$other_users_container.append(html);
                }
                this.update_padding();
            }
            return;
        }

        if (new_pos_in_all_users < this.render_count) {
            this.render_count += 1;
            const $li = this.find_li({key: user_id_following_insertion});
            $li.before(html);
            this.update_padding();
        }
    }

    insert_or_move(opts) {
        const user_id = opts.user_id;
        const item = opts.item;

        this.maybe_remove_user_id({user_id});

        const new_pos_in_all_users = this.find_position({
            user_id,
            user_id_list: this.all_user_ids,
        });

        const current_sub = narrow_state.stream_sub();
        const pm_ids_set = narrow_state.pm_ids_set();
        const is_subscribed_user = buddy_data.user_matches_narrow(
            user_id,
            pm_ids_set,
            current_sub?.stream_id,
        );
        const user_id_list = is_subscribed_user
            ? this.users_matching_view_ids
            : this.other_user_ids;
        const new_pos_in_user_list = this.find_position({
            user_id,
            user_id_list,
        });

        // Order is important here--get the new_user_id
        // before mutating our list.  An undefined value
        // corresponds to appending.
        const new_user_id = user_id_list[new_pos_in_user_list];

        user_id_list.splice(new_pos_in_user_list, 0, user_id);
        this.all_user_ids.splice(new_pos_in_all_users, 0, user_id);

        const html = this.item_to_html({item});
        this.insert_new_html({
            new_pos_in_all_users,
            html,
            new_user_id,
            is_subscribed_user,
        });
    }

    fill_screen_with_content() {
        let height = this.height_to_fill();

        const elem = scroll_util
            .get_scroll_element($(this.scroll_container_selector))
            .expectOne()[0];

        // Add a fudge factor.
        height += 10;

        while (this.render_count < this.all_user_ids.length) {
            const padding_height = $(this.padding_selector).height();
            const bottom_offset = elem.scrollHeight - elem.scrollTop - padding_height;

            if (bottom_offset > height) {
                break;
            }

            const chunk_size = 20;

            this.render_more({
                chunk_size,
            });
        }
    }

    // This is a bit of a hack to make sure we at least have
    // an empty list to start, before we get the initial payload.
    $users_matching_view_container = $(this.matching_view_list_selector);
    $other_users_container = $(this.other_user_list_selector);

    start_scroll_handler() {
        // We have our caller explicitly call this to make
        // sure everything's in place.
        const $scroll_container = scroll_util.get_scroll_element($(this.scroll_container_selector));

        $scroll_container.on("scroll", () => {
            this.fill_screen_with_content();
        });
    }

    update_padding() {
        padded_widget.update_padding({
            shown_rows: this.render_count,
            total_rows: this.all_user_ids.length,
            content_selector: "#buddy_list_wrapper",
            padding_selector: this.padding_selector,
        });
    }
}

export const buddy_list = new BuddyList();
