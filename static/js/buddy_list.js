import $ from "jquery";

import render_presence_row from "../templates/presence_row.hbs";
import render_presence_rows from "../templates/presence_rows.hbs";
import render_presence_sections from "../templates/presence_sections.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import {$t} from "./i18n";
import {localstorage} from "./localstorage";
import * as message_viewport from "./message_viewport";
import * as padded_widget from "./padded_widget";
import * as ui from "./ui";

const ls = localstorage();

class BuddyListConf {
    container_sel = "#user_presences";
    scroll_container_sel = "#buddy_list_wrapper";
    item_sel = "li.user_sidebar_entry";
    padding_sel = "#buddy_list_wrapper_padding";
    users_section_sel = "#users";
    others_section_sel = "#others";

    sections_to_html(opts) {
        let users_title_collapsed = false;
        let others_title_collapsed = false;
        if (localstorage.supported()) {
            users_title_collapsed = Boolean(ls.get("users_title_collapsed"));
            others_title_collapsed = Boolean(ls.get("others_title_collapsed"));
        }
        const html = render_presence_sections({
            users_count: $t({defaultMessage: " {users_count}"}, {users_count: opts.users_count}),
            users_title: opts.user_items_title,
            users_title_collapsed,
            others_count: $t(
                {defaultMessage: " {others_count}"},
                {others_count: opts.others_count},
            ),
            others_title: opts.other_items_title,
            others_title_collapsed,
        });
        return html;
    }

    items_to_html(opts) {
        const html = render_presence_rows({presence_rows: opts.items});
        return html;
    }

    item_to_html(opts) {
        const html = render_presence_row(opts.item);
        return html;
    }

    get_li_from_key(opts) {
        const user_id = opts.key;
        const $container = $(this.container_sel);
        return $container.find(`${this.item_sel}[data-user-id='${CSS.escape(user_id)}']`);
    }

    get_key_from_li(opts) {
        return Number.parseInt(opts.$li.expectOne().attr("data-user-id"), 10);
    }

    get_data_from_keys(opts) {
        const keys = opts.keys;
        const data = buddy_data.get_items_for_people(keys);
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
    user_keys = [];
    other_keys = [];

    populate(opts) {
        this.is_all_user_list = false;
        this.users_render_count = 0;
        this.others_render_count = 0;
        this.$container.html("");

        // We rely on our caller to give us items
        // in already-sorted order.
        this.user_keys = opts.user_keys;
        this.other_keys = opts.other_keys;

        const html = this.sections_to_html({
            user_items_title: opts.user_keys_title,
            users_count: opts.user_keys.length,
            other_items_title: opts.other_keys_title,
            others_count: opts.other_keys.length,
        });

        this.$container = $(this.container_sel);

        // todo: optimize append calls
        // We should really avoid appending twice because of performance reasons, it might
        // be as simple as passing the html we've made here to fill_screen_with_content and
        // moving this append to the container, after fill_screen_with_content. Or maybe not?
        this.$container.append(html);

        if (localstorage.supported()) {
            $(this.users_section_sel)
                .off("show")
                .on("show", () => {
                    ls.set("users_title_collapsed", false);
                });
            $(this.users_section_sel)
                .off("hide")
                .on("hide", () => {
                    ls.set("users_title_collapsed", true);
                });
            $(this.others_section_sel)
                .off("show")
                .on("show", () => {
                    ls.set("others_title_collapsed", false);
                });
            $(this.others_section_sel)
                .off("hide")
                .on("hide", () => {
                    ls.set("others_title_collapsed", true);
                });
        }
        $(this.users_section_sel)
            .off("shown")
            .on("shown", () => {
                // render elements if both sections were initialized as collapsed and this is the
                // first to be un-collapsed
                this.is_all_user_list = false;
                this.fill_screen_with_content();
                this.update_padding();
            });
        $(this.users_section_sel)
            .off("hidden")
            .on("hidden", () => {
                // handles the case where we have the others section un-collapsed, but it has nothing
                // rendered since the users section is taking up the full height of the view and we
                // then collapse the users section.
                this.is_all_user_list = false;
                this.fill_screen_with_content();
                this.update_padding();
            });
        $(this.others_section_sel)
            .off("shown")
            .on("shown", () => {
                // render elements if both sections were initialized as collapsed and this is the
                // first to be un-collapsed
                this.is_all_user_list = false;
                this.fill_screen_with_content();
                this.update_padding();
            });
        $(this.others_section_sel)
            .off("hidden")
            .on("hidden", () => {
                // handles the case where the users section is collapsed, and the others section is
                // taking up the full height of the view, and the others section is collapsed
                // note that we only need to adjust the padding
                this.update_padding();
            });

        // we're populating the all users list if there
        // is no user title
        this.is_all_user_list = !opts.user_keys_title;
        this.fill_screen_with_content();
    }

    _render_more({chunk_size, begin, keys, section_sel}) {
        const end = begin + chunk_size;
        const more_keys = keys.slice(begin, end);

        if (more_keys.length === 0) {
            return 0;
        }

        const items = this.get_data_from_keys({
            keys: more_keys,
        });

        const html = this.items_to_html({
            items,
        });

        this.$section = $(section_sel);
        this.$section.append(html);

        // Invariant: more_keys.length >= items.length.
        // (Usually they're the same, but occasionally keys
        // won't return valid items.  Even though we don't
        // actually render these keys, we still "count" them
        // as rendered.
        return more_keys.length;
    }

    users_render_more(opts) {
        const render_count = this._render_more({
            chunk_size: opts.chunk_size,
            begin: this.users_render_count,
            keys: this.user_keys,
            section_sel: this.users_section_sel,
        });
        if (render_count > 0) {
            this.users_render_count += render_count;
            this.update_padding();
        }
    }

    others_render_more(opts) {
        const render_count = this._render_more({
            chunk_size: opts.chunk_size,
            begin: this.others_render_count,
            keys: this.other_keys,
            section_sel: this.others_section_sel,
        });
        if (render_count > 0) {
            this.others_render_count += render_count;
            this.update_padding();
        }
    }

    get_items() {
        const $obj = this.$container.find(`${this.item_sel}`);
        return $obj.map((i, elem) => $(elem));
    }

    first_key() {
        if (!ls.get("users_title_collapsed")) {
            return this.user_keys[0];
        }
        if (!ls.get("others_title_collapsed")) {
            return this.other_keys[0];
        }
        return undefined;
    }

    prev_key(key) {
        let i = this.other_keys.indexOf(key);

        if (i < 0) {
            // if the key is not found in the other_keys,
            // look through the user_keys
            i = this.user_keys.indexOf(key);
            if (i < 0) {
                return undefined;
            }
            return this.user_keys[i - 1];
        }

        if (i === 0 && !ls.get("users_title_collapsed")) {
            // if key happens to be the first element in other_keys,
            // and the users section is not collapsed,
            // return the last user_key, rather than undefined.
            return this.user_keys[this.user_keys.length - 1];
        }

        return this.other_keys[i - 1];
    }

    next_key(key) {
        let i = this.user_keys.indexOf(key);

        if (i < 0) {
            // if the key is not found in the user_keys,
            // look through the other_keys
            i = this.other_keys.indexOf(key);
            if (i < 0) {
                return undefined;
            }
            return this.other_keys[i + 1];
        }

        if (i === this.user_keys.length - 1 && !ls.get("others_title_collapsed")) {
            // if key happens to be the last element in user_keys,
            // and the others section is not collapsed,
            // return the first other_key, rather than undefined.
            return this.other_keys[0];
        }

        return this.user_keys[i + 1];
    }

    maybe_remove_key(opts) {
        this.maybe_remove_user_key(opts);
        this.maybe_remove_other_key(opts);
    }

    maybe_remove_user_key(opts) {
        const pos = this.user_keys.indexOf(opts.key);

        if (pos < 0) {
            return;
        }

        this.user_keys.splice(pos, 1);

        if (pos < this.users_render_count) {
            this.users_render_count -= 1;
            this._remove_key_and_update_padding(opts);
        }
    }

    _remove_key_and_update_padding(opts) {
        const $li = this.find_li({key: opts.key});
        $li.remove();
        this.update_padding();
    }

    maybe_remove_other_key(opts) {
        const pos = this.other_keys.indexOf(opts.key);

        if (pos < 0) {
            return;
        }

        this.other_keys.splice(pos, 1);

        if (pos < this.others_render_count) {
            this.others_render_count -= 1;
            this._remove_key_and_update_padding(opts);
        }
    }

    _find_position({key, keys}) {
        let i;

        for (i = 0; i < keys.length; i += 1) {
            const list_key = keys[i];

            if (this.compare_function(key, list_key) < 0) {
                return i;
            }
        }

        return keys.length;
    }

    find_user_position(opts) {
        return this._find_position({
            key: opts.key,
            keys: this.user_keys,
        });
    }

    find_other_position(opts) {
        return this._find_position({
            key: opts.key,
            keys: this.other_keys,
        });
    }

    force_render_users(opts) {
        const pos = opts.pos;

        // Try to render a bit optimistically here.
        const cushion_size = 3;
        const chunk_size = pos + cushion_size - this.users_render_count;

        if (chunk_size <= 0) {
            blueslip.error("cannot show key at this position: " + pos);
        }

        this.users_render_more({
            chunk_size,
        });
    }

    force_render_others(opts) {
        const pos = opts.pos;

        // Try to render a bit optimistically here.
        const cushion_size = 3;
        const chunk_size = pos + cushion_size - this.others_render_count;

        if (chunk_size <= 0) {
            blueslip.error("cannot show key at this position: " + pos);
        }

        this.others_render_more({
            chunk_size,
        });
    }

    find_li(opts) {
        const key = opts.key;

        // Try direct DOM lookup first for speed.
        let $li = this.get_li_from_key({
            key,
        });

        if ($li.length === 1) {
            return $li;
        }

        if (!opts.force_render) {
            // Most callers don't force us to render a list
            // item that wouldn't be on-screen anyway.
            return $li;
        }

        let pos = this.user_keys.indexOf(key);

        if (pos < 0) {
            pos = this.other_keys.indexOf(key);
            if (pos < 0) {
                // TODO: See ListCursor.get_row() for why this is
                //       a bit janky now.
                return [];
            }
            this.force_render_others({
                pos,
            });
        } else {
            this.force_render_users({
                pos,
            });
        }

        $li = this.get_li_from_key({
            key,
        });

        return $li;
    }

    insert_new_html_for_user(opts) {
        const new_key = opts.new_key;
        const html = opts.html;
        const pos = opts.pos;

        if (new_key === undefined) {
            if (pos === this.users_render_count) {
                this.users_render_count += 1;
                this.$users_section.append(html);
                this.update_padding();
            }
            return;
        }

        if (pos < this.users_render_count) {
            this.users_render_count += 1;
            const $li = this.find_li({key: new_key});
            $li.before(html);
            this.update_padding();
        }
    }

    insert_new_html_for_other(opts) {
        const new_key = opts.new_key;
        const html = opts.html;
        const pos = opts.pos;

        if (new_key === undefined) {
            if (pos === this.others_render_count) {
                this.others_render_count += 1;
                this.$others_section.append(html);
                this.update_padding();
            }
            return;
        }

        if (pos < this.others_render_count) {
            this.others_render_count += 1;
            const row = this.find_li({key: new_key});
            row.before(html);
            this.update_padding();
        }
    }

    insert_or_move(opts) {
        // move is just remove then insert
        this.maybe_remove_key({key: opts.key});
        this.insert_user_or_other(opts);
    }

    insert_user_or_other(opts) {
        const section = buddy_data.does_belong_to_users_or_others_section(opts.key);
        switch (section) {
            case "users":
                this.insert_user(opts);
                break;
            case "others":
                this.insert_other(opts);
                break;
            default:
                blueslip.error("asked to insert but user does not belong inside either section.");
        }
    }

    insert_user(opts) {
        const key = opts.key;
        const item = opts.item;

        const pos = this.find_user_position({
            key,
        });

        // Order is important here--get the new_key
        // before mutating our list.  An undefined value
        // corresponds to appending.
        const new_key = this.user_keys[pos];

        this.user_keys.splice(pos, 0, key);

        const html = this.item_to_html({item});
        this.insert_new_html_for_user({
            pos,
            html,
            new_key,
        });
    }

    insert_other(opts) {
        const key = opts.key;
        const item = opts.item;

        const pos = this.find_other_position({
            key,
        });

        // Order is important here--get the new_key
        // before mutating our list.  An undefined value
        // corresponds to appending.
        const new_key = this.other_keys[pos];

        this.other_keys.splice(pos, 0, key);

        const html = this.item_to_html({item});
        this.insert_new_html_for_other({
            pos,
            html,
            new_key,
        });
    }

    fill_screen_with_content() {
        let height = this.height_to_fill();

        const elem = ui.get_scroll_element($(this.scroll_container_sel)).expectOne()[0];

        // Add a fudge factor.
        height += 10;

        const chunk_size = 20;

        if (this.is_all_user_list) {
            while (this.users_render_count < this.user_keys.length) {
                const padding_height = $(this.padding_sel).height();
                const bottom_offset = elem.scrollHeight - elem.scrollTop - padding_height;

                if (bottom_offset > height) {
                    break;
                }

                // we just use the users_render_more for the all users list
                this.users_render_more({
                    chunk_size,
                });
            }
        } else {
            const is_users_title_collapsed = ls.get("users_title_collapsed");
            const is_others_title_collapsed = ls.get("others_title_collapsed");
            if (is_users_title_collapsed && this.users_render_count === 0) {
                // render at least 1 user so that show and shown can trigger properly
                this.users_render_more({chunk_size: 1});
            }
            while (!is_users_title_collapsed && this.users_render_count < this.user_keys.length) {
                const padding_height = $(this.padding_sel).height();

                // we're using a user_section_elem instead of the scroll elem to handle the case where
                // we have the users section collapsed, and the others section un-collapsed and taking
                // up the full height of the view and we then un-collapse the users section.
                const user_section_elem = $(this.users_section_sel)[0];
                const bottom_offset =
                    user_section_elem.scrollHeight - elem.scrollTop - padding_height;
                if (bottom_offset > height) {
                    break;
                }

                this.users_render_more({
                    chunk_size,
                });
            }
            if (is_others_title_collapsed && this.others_render_count === 0) {
                // render at least 1 other so that show and shown can trigger properly
                this.others_render_more({chunk_size: 1});
            }
            if (this.users_render_count >= this.user_keys.length || is_users_title_collapsed) {
                while (
                    !is_others_title_collapsed &&
                    this.others_render_count < this.other_keys.length
                ) {
                    const padding_height = $(this.padding_sel).height();
                    const bottom_offset = elem.scrollHeight - elem.scrollTop - padding_height;

                    if (bottom_offset > height) {
                        break;
                    }

                    this.others_render_more({
                        chunk_size,
                    });
                }
            }
        }
    }

    // This is a bit of a hack to make sure we at least have
    // an empty list to start, before we get the initial payload.
    $container = $(this.container_sel);
    $users_section = $(this.users_section_sel);
    $others_section = $(this.others_section_sel);

    start_scroll_handler() {
        // We have our caller explicitly call this to make
        // sure everything's in place.
        const $scroll_container = ui.get_scroll_element($(this.scroll_container_sel));

        $scroll_container.on("scroll", () => {
            this.fill_screen_with_content();
        });
    }

    update_padding() {
        const is_users_title_collapsed = ls.get("users_title_collapsed");
        const is_others_title_collapsed = ls.get("others_title_collapsed");
        let shown_rows = 0;
        let total_rows = 0;
        if (!is_users_title_collapsed) {
            shown_rows += this.users_render_count;
            total_rows += this.user_keys.length;
        }
        if (!is_others_title_collapsed) {
            shown_rows += this.others_render_count;
            total_rows += this.other_keys.length;
        }
        padded_widget.update_padding({
            shown_rows,
            total_rows,
            content_sel: this.container_sel,
            padding_sel: this.padding_sel,
        });
    }
}

export const buddy_list = new BuddyList();
