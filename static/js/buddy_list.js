var buddy_list = (function () {

function buddy_list_conf() {
    var conf = {};

    conf.container_sel = '#user_presences';
    conf.scroll_container_sel = '#buddy_list_wrapper';
    conf.item_sel = 'li.user_sidebar_entry';
    conf.padding_sel = '#buddy_list_wrapper_padding';

    conf.items_to_html = function (opts) {
        var user_info = opts.items;
        var html = templates.render('user_presence_rows', {users: user_info});
        return html;
    };

    conf.item_to_html = function (opts) {
        var html = templates.render('user_presence_row', opts.item);
        return html;
    };

    conf.get_li_from_key = function (opts) {
        var user_id = opts.key;
        var container = $(conf.container_sel);
        var sel = conf.item_sel + "[data-user-id='" + user_id + "']";
        return container.find(sel);
    };

    conf.get_key_from_li = function (opts) {
        var user_id = opts.li.expectOne().attr('data-user-id');
        return user_id;
    };

    conf.get_data_from_keys = function (opts) {
        var keys = opts.keys;
        var data = buddy_data.get_items_for_users(keys);
        return data;
    };

    conf.compare_function = buddy_data.compare_function;

    conf.height_to_fill = function () {
        // Because the buddy list gets sized dynamically, we err on the side
        // of using the height of the entire viewport for deciding
        // how much content to render.  Even on tall monitors this should
        // still be a significant optimization for orgs with thousands of
        // users.
        var height = message_viewport.height();
        return height;
    };

    return conf;
}

function buddy_list_create() {
    var conf = buddy_list_conf();

    var self = {};

    self.container_sel = conf.container_sel;
    self.scroll_container_sel = conf.scroll_container_sel;
    self.item_sel = conf.item_sel;
    self.padding_sel = conf.padding_sel;

    var func_names = [
        'items_to_html',
        'item_to_html',
        'get_li_from_key',
        'get_key_from_li',
        'get_data_from_keys',
        'compare_function',
        'height_to_fill',
    ];

    _.each(func_names, function (func_name) {
        self[func_name] = conf[func_name];
    });

    self.keys = [];

    self.populate = function (opts) {
        self.render_count = 0;
        self.container.html('');

        // We rely on our caller to give us items
        // in already-sorted order.
        self.keys = _.map(opts.keys, function (k) {
            return k.toString();
        });

        self.fill_screen_with_content();
    };

    self.render_more = function (opts) {
        var chunk_size = opts.chunk_size;

        var begin = self.render_count;
        var end = begin + chunk_size;

        var more_keys = self.keys.slice(begin, end);

        if (more_keys.length === 0) {
            return;
        }

        var items = self.get_data_from_keys({
            keys: more_keys,
        });

        var html = self.items_to_html({
            items: items,
        });
        self.container = $(self.container_sel);
        self.container.append(html);

        // Invariant: more_keys.length >= items.length.
        // (Usually they're the same, but occasionally keys
        // won't return valid items.  Even though we don't
        // actually render these keys, we still "count" them
        // as rendered.

        self.render_count += more_keys.length;
        self.update_padding();
    };

    self.get_items = function () {
        var obj = self.container.find(self.item_sel);
        return obj.map(function (i, elem) {
            return $(elem);
        });
    };

    self.first_key = function () {
        return self.keys[0];
    };

    self.prev_key = function (key) {
        var i = self.keys.indexOf(key.toString());

        if (i <= 0) {
            return;
        }

        return self.keys[i - 1];
    };

    self.next_key = function (key) {
        var i = self.keys.indexOf(key.toString());

        if (i < 0) {
            return;
        }

        return self.keys[i + 1];
    };

    self.maybe_remove_key = function (opts) {
        var pos = self.keys.indexOf(opts.key);

        if (pos < 0) {
            return;
        }

        self.keys.splice(pos, 1);

        if (pos < self.render_count) {
            self.render_count -= 1;
            var li = self.find_li({key: opts.key});
            li.remove();
            self.update_padding();
        }
    };

    self.find_position = function (opts) {
        var key = opts.key;
        var i;

        for (i = 0; i < self.keys.length; i += 1) {
            var list_key = self.keys[i];

            if (self.compare_function(key, list_key) < 0) {
                return i;
            }
        }

        return self.keys.length;
    };

    self.force_render = function (opts) {
        var pos = opts.pos;

        // Try to render a bit optimistically here.
        var cushion_size = 3;
        var chunk_size = pos + cushion_size - self.render_count;

        if (chunk_size <= 0) {
            blueslip.error('cannot show key at this position: ' + pos);
        }

        self.render_more({
            chunk_size: chunk_size,
        });
    };

    self.find_li = function (opts) {
        var key = opts.key.toString();

        // Try direct DOM lookup first for speed.
        var li = self.get_li_from_key({
            key: key,
        });

        if (li.length === 1) {
            return li;
        }

        if (!opts.force_render) {
            // Most callers don't force us to render a list
            // item that wouldn't be on-screen anyway.
            return li;
        }

        var pos = self.keys.indexOf(key);

        if (pos < 0) {
            // TODO: See list_cursor.get_row() for why this is
            //       a bit janky now.
            return [];
        }

        self.force_render({
            pos: pos,
        });

        li = self.get_li_from_key({
            key: key,
        });

        return li;
    };

    self.insert_new_html = function (opts) {
        var other_key = opts.other_key;
        var html = opts.html;
        var pos = opts.pos;

        if (other_key === undefined) {
            if (pos === self.render_count) {
                self.render_count += 1;
                self.container.append(html);
                self.update_padding();
            }
            return;
        }

        if (pos < self.render_count) {
            self.render_count += 1;
            var li = self.find_li({key: other_key});
            li.before(html);
            self.update_padding();
        }
    };

    self.insert_or_move = function (opts) {
        var key = opts.key.toString();
        var item = opts.item;

        self.maybe_remove_key({key: key});

        var pos = self.find_position({
            key: key,
        });

        // Order is important here--get the other_key
        // before mutating our list.  An undefined value
        // corresponds to appending.
        var other_key = self.keys[pos];

        self.keys.splice(pos, 0, key);

        var html = self.item_to_html({item: item});
        self.insert_new_html({
            pos: pos,
            html: html,
            other_key: other_key,
        });
    };

    self.fill_screen_with_content = function () {
        var height_to_fill = self.height_to_fill();

        var elem = $(self.scroll_container_sel).expectOne()[0];

        // Add a fudge factor.
        height_to_fill += 10;

        while (self.render_count < self.keys.length) {
            var padding_height = $(self.padding_sel).height();
            var bottom_offset = elem.scrollHeight - elem.scrollTop - padding_height;

            if (bottom_offset > height_to_fill) {
                break;
            }

            var chunk_size = 20;

            self.render_more({
                chunk_size: chunk_size,
            });
        }
    };

    // This is a bit of a hack to make sure we at least have
    // an empty list to start, before we get the initial payload.
    self.container = $(self.container_sel);

    self.start_scroll_handler = function () {
        // We have our caller explicitly call this to make
        // sure everything's in place.
        var scroll_container = $(self.scroll_container_sel);

        scroll_container.scroll(function () {
            self.fill_screen_with_content();
        });
    };

    self.update_padding = function () {
        padded_widget.update_padding({
            shown_rows: self.render_count,
            total_rows: self.keys.length,
            content_sel: self.container_sel,
            padding_sel: self.padding_sel,
        });
    };

    return self;
}

var exports = buddy_list_create();

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = buddy_list;
}

window.buddy_list = buddy_list;
