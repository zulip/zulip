"use strict";

const render_user_presence_row = require("../templates/user_presence_row.hbs");
const render_user_presence_rows = require("../templates/user_presence_rows.hbs");

class BuddyListConf {
    container_sel = "#user_presences";
    scroll_container_sel = "#buddy_list_wrapper";
    item_sel = "li.user_sidebar_entry";
    padding_sel = "#buddy_list_wrapper_padding";

    items_to_html(opts) {
        const user_info = opts.items;
        const html = render_user_presence_rows({users: user_info});
        return html;
    }

    item_to_html(opts) {
        const html = render_user_presence_row(opts.item);
        return html;
    }

    get_li_from_key(opts) {
        const user_id = opts.key;
        const container = $(this.container_sel);
        const sel = this.item_sel + "[data-user-id='" + user_id + "']";
        return container.find(sel);
    }

    get_key_from_li(opts) {
        return Number.parseInt(opts.li.expectOne().attr("data-user-id"), 10);
    }

    get_data_from_keys(opts) {
        const keys = opts.keys;
        const data = buddy_data.get_items_for_users(keys);
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

class BuddyList extends BuddyListConf {
    keys = [];

    populate(opts) {
        this.render_count = 0;
        this.container.html("");

        // We rely on our caller to give us items
        // in already-sorted order.
        this.keys = opts.keys;

        this.fill_screen_with_content();
    }

    render_more(opts) {
        const chunk_size = opts.chunk_size;

        const begin = this.render_count;
        const end = begin + chunk_size;

        const more_keys = this.keys.slice(begin, end);

        if (more_keys.length === 0) {
            return;
        }

        const items = this.get_data_from_keys({
            keys: more_keys,
        });

        const html = this.items_to_html({
            items,
        });
        this.container = $(this.container_sel);
        this.container.append(html);

        // Invariant: more_keys.length >= items.length.
        // (Usually they're the same, but occasionally keys
        // won't return valid items.  Even though we don't
        // actually render these keys, we still "count" them
        // as rendered.

        this.render_count += more_keys.length;
        this.update_padding();
    }

    get_items() {
        const obj = this.container.find(this.item_sel);
        return obj.map((i, elem) => $(elem));
    }

    first_key() {
        return this.keys[0];
    }

    prev_key(key) {
        const i = this.keys.indexOf(key);

        if (i <= 0) {
            return undefined;
        }

        return this.keys[i - 1];
    }

    next_key(key) {
        const i = this.keys.indexOf(key);

        if (i < 0) {
            return undefined;
        }

        return this.keys[i + 1];
    }

    maybe_remove_key(opts) {
        const pos = this.keys.indexOf(opts.key);

        if (pos < 0) {
            return;
        }

        this.keys.splice(pos, 1);

        if (pos < this.render_count) {
            this.render_count -= 1;
            const li = this.find_li({key: opts.key});
            li.remove();
            this.update_padding();
        }
    }

    find_position(opts) {
        const key = opts.key;
        let i;

        for (i = 0; i < this.keys.length; i += 1) {
            const list_key = this.keys[i];

            if (this.compare_function(key, list_key) < 0) {
                return i;
            }
        }

        return this.keys.length;
    }

    force_render(opts) {
        const pos = opts.pos;

        // Try to render a bit optimistically here.
        const cushion_size = 3;
        const chunk_size = pos + cushion_size - this.render_count;

        if (chunk_size <= 0) {
            blueslip.error("cannot show key at this position: " + pos);
        }

        this.render_more({
            chunk_size,
        });
    }

    find_li(opts) {
        const key = opts.key;

        // Try direct DOM lookup first for speed.
        let li = this.get_li_from_key({
            key,
        });

        if (li.length === 1) {
            return li;
        }

        if (!opts.force_render) {
            // Most callers don't force us to render a list
            // item that wouldn't be on-screen anyway.
            return li;
        }

        const pos = this.keys.indexOf(key);

        if (pos < 0) {
            // TODO: See ListCursor.get_row() for why this is
            //       a bit janky now.
            return [];
        }

        this.force_render({
            pos,
        });

        li = this.get_li_from_key({
            key,
        });

        return li;
    }

    insert_new_html(opts) {
        const other_key = opts.other_key;
        const html = opts.html;
        const pos = opts.pos;

        if (other_key === undefined) {
            if (pos === this.render_count) {
                this.render_count += 1;
                this.container.append(html);
                this.update_padding();
            }
            return;
        }

        if (pos < this.render_count) {
            this.render_count += 1;
            const li = this.find_li({key: other_key});
            li.before(html);
            this.update_padding();
        }
    }

    insert_or_move(opts) {
        const key = opts.key;
        const item = opts.item;

        this.maybe_remove_key({key});

        const pos = this.find_position({
            key,
        });

        // Order is important here--get the other_key
        // before mutating our list.  An undefined value
        // corresponds to appending.
        const other_key = this.keys[pos];

        this.keys.splice(pos, 0, key);

        const html = this.item_to_html({item});
        this.insert_new_html({
            pos,
            html,
            other_key,
        });
    }

    fill_screen_with_content() {
        let height = this.height_to_fill();

        const elem = ui.get_scroll_element($(this.scroll_container_sel)).expectOne()[0];

        // Add a fudge factor.
        height += 10;

        while (this.render_count < this.keys.length) {
            const padding_height = $(this.padding_sel).height();
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
    container = $(this.container_sel);

    start_scroll_handler() {
        // We have our caller explicitly call this to make
        // sure everything's in place.
        const scroll_container = ui.get_scroll_element($(this.scroll_container_sel));

        scroll_container.on("scroll", () => {
            this.fill_screen_with_content();
        });
    }

    update_padding() {
        padded_widget.update_padding({
            shown_rows: this.render_count,
            total_rows: this.keys.length,
            content_sel: this.container_sel,
            padding_sel: this.padding_sel,
        });
    }
}

const buddy_list = new BuddyList();

module.exports = buddy_list;

window.buddy_list = buddy_list;
