var list_cursor = function (opts) {
    var self = {};

    var config_ok =
        opts.highlight_class &&
        opts.list &&
        opts.list.scroll_container_sel &&
        opts.list.find_li &&
        opts.list.first_key &&
        opts.list.prev_key &&
        opts.list.next_key
    ;

    if (!config_ok) {
        blueslip.error('Programming error');
        return;
    }

    self.clear = function () {
        if (self.curr_key === undefined) {
            return;
        }
        var row = self.get_row(self.curr_key);
        if (row) {
            row.clear();
        }
        self.curr_key = undefined;
    };

    self.get_key = function () {
        return self.curr_key;
    };

    self.get_row = function (key) {
        // TODO: The list class should probably do more of the work
        //       here, so we're not so coupled to jQuery, and
        //       so we instead just get back a widget we can say
        //       something like widget.select() on.  This will
        //       be especially important if we do lazy rendering.
        //       It would also give the caller more flexibility on
        //       the actual styling.
        if (key === undefined) {
            return;
        }

        var li = opts.list.find_li({
            key: key,
            force_render: true,
        });

        if (li.length === 0) {
            return;
        }

        return {
            highlight: function () {
                li.addClass(opts.highlight_class);
                self.adjust_scroll(li);
            },
            clear: function () {
                li.removeClass(opts.highlight_class);
            },
        };
    };

    self.adjust_scroll = function (li) {
        var scroll_container = $(opts.list.scroll_container_sel);
        scroll_util.scroll_element_into_container(li, scroll_container);
    };

    self.redraw = function () {
        // We should only call this for situations like the buddy
        // list where we redraw the whole list without necessarily
        // changing it, so we just want to re-highlight the current
        // row in the new DOM.  If you are filtering, for now you
        // should call the 'reset()' method.
        var row = self.get_row(self.curr_key);

        if (row === undefined) {
            return;
        }
        row.highlight();
    };

    self.go_to = function (key) {
        if (key === undefined) {
            blueslip.error('Caller is not checking keys for list_cursor.go_to');
            return;
        }
        if (key === self.curr_key) {
            return;
        }
        self.clear();
        var row = self.get_row(key);
        if (row === undefined) {
            blueslip.error('Cannot highlight key for list_cursor: ' + key);
            return;
        }
        self.curr_key = key;
        row.highlight();
    };

    self.reset = function () {
        self.clear();
        var key = opts.list.first_key();
        if (key === undefined) {
            self.curr_key = undefined;
            return;
        }
        self.go_to(key);
    };

    self.prev = function () {
        if (self.curr_key === undefined) {
            return;
        }
        var key = opts.list.prev_key(self.curr_key);
        if (key === undefined) {
            // leave the current key
            return;
        }
        self.go_to(key);
    };

    self.next = function () {
        if (self.curr_key === undefined) {
            // This is sort of a special case where we went from
            // an empty filter to having data.
            self.reset();
            return;
        }
        var key = opts.list.next_key(self.curr_key);
        if (key === undefined) {
            // leave the current key
            return;
        }
        self.go_to(key);
    };

    return self;
};
if (typeof module !== 'undefined') {
    module.exports = list_cursor;
}
window.list_cursor = list_cursor;
