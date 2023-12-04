import $ from "jquery";

import render_presence_row from "../templates/presence_row.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import * as message_viewport from "./message_viewport";
import * as padded_widget from "./padded_widget";
import * as scroll_util from "./scroll_util";

class BuddyListConf {
    container_selector = "#buddy-list-users-matching-view";
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
        const $container = $(this.container_selector);
        return $container.find(`${this.item_selector}[data-user-id='${CSS.escape(user_id)}']`);
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

    populate(opts) {
        this.render_count = 0;
        this.$container.empty();

        // We rely on our caller to give us items
        // in already-sorted order.
        this.all_user_ids = opts.all_user_ids;

        this.fill_screen_with_content();
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

        const html = this.items_to_html({
            items,
        });
        this.$container = $(this.container_selector);
        this.$container.append(html);

        // Invariant: more_user_ids.length >= items.length.
        // (Usually they're the same, but occasionally user ids
        // won't return valid items.  Even though we don't
        // actually render these user ids, we still "count" them
        // as rendered.

        this.render_count += more_user_ids.length;
        this.update_padding();
    }

    get_items() {
        const $obj = this.$container.find(`${this.item_selector}`);
        return $obj.map((_i, elem) => $(elem));
    }

    // From `type List<Key>`, where the key is a user_id.
    first_key() {
        return this.all_user_ids[0];
    }

    // From `type List<Key>`, where the key is a user_id.
    prev_key(key) {
        const i = this.all_user_ids.indexOf(key);

        if (i <= 0) {
            return undefined;
        }

        return this.all_user_ids[i - 1];
    }

    // From `type List<Key>`, where the key is a user_id.
    next_key(key) {
        const i = this.all_user_ids.indexOf(key);

        if (i < 0) {
            return undefined;
        }

        return this.all_user_ids[i + 1];
    }

    maybe_remove_user_id(opts) {
        const pos = this.all_user_ids.indexOf(opts.user_id);

        if (pos < 0) {
            return;
        }

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

        for (i = 0; i < this.all_user_ids.length; i += 1) {
            const list_user_id = this.all_user_ids[i];

            if (this.compare_function(user_id, list_user_id) < 0) {
                return i;
            }
        }

        return this.all_user_ids.length;
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
        const new_pos_in_all_users = opts.pos;

        if (user_id_following_insertion === undefined) {
            if (new_pos_in_all_users === this.render_count) {
                this.render_count += 1;
                this.$container.append(html);
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

        const pos = this.find_position({
            user_id,
        });

        // Order is important here--get the new_user_id
        // before mutating our list.  An undefined value
        // corresponds to appending.
        const new_user_id = this.all_user_ids[pos];

        this.all_user_ids.splice(pos, 0, user_id);

        const html = this.item_to_html({item});
        this.insert_new_html({
            pos,
            html,
            new_user_id,
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
    $container = $(this.container_selector);

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
            content_selector: this.container_selector,
            padding_selector: this.padding_selector,
        });
    }
}

export const buddy_list = new BuddyList();
