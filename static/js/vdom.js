exports.eq_array = (a, b, eq) => {
    if (a === b) {
        // either both are undefined, or they
        // are referentially equal
        return true;
    }

    if (a === undefined || b === undefined) {
        return false;
    }

    if (a.length !== b.length) {
        return false;
    }

    return _.all(a, (item, i) => {
        return eq(item, b[i]);
    });
};

exports.ul = (opts) => {
    return {
        tag_name: 'ul',
        opts: opts,
    };
};

exports.render_tag = (tag) => {
    /*
        This renders a tag into a string.  It will
        automatically escape attributes, but it's your
        responsibility to make sure keyed_nodes provide
        a `render` method that escapes HTML properly.
        (One option is to use templates.)

        Do NOT call this method directly, except for
        testing.  The vdom scheme expects you to use
        the `update` method.
    */
    const opts = tag.opts;
    const tag_name = tag.tag_name;
    const attr_str = _.map(opts.attrs, (attr) => {
        return ' ' + attr[0] + '="' + util.escape_html(attr[1]) + '"';
    }).join('');

    const start_tag = '<' + tag_name + attr_str + '>';
    const end_tag = '</' + tag_name + '>';

    if (opts.keyed_nodes === undefined) {
        blueslip.error("We need keyed_nodes to render innards.");
        return;
    }

    const innards = _.map(opts.keyed_nodes, (node) => {
        return node.render();
    }).join('\n');
    return start_tag + '\n' + innards + '\n' + end_tag;
};

exports.update = (replace_content, find, new_dom, old_dom) => {
    /*
        The update method allows you to continually
        update a "virtual" representation of your DOM,
        and then this method actually updates the
        real DOM using jQuery.  The caller will pass
        in a method called `replace_content` that will replace
        the entire html and a method called `find` to
        find the existing DOM for more surgical updates.

        The first "update" will be more like a create,
        because your `old_dom` should be undefined.
        After that initial call, it is important that
        you always pass in a correct value of `old_dom`;
        otherwise, things will be incredibly confusing.

        The basic scheme here is simple:

            1) If old_dom is undefined, we render
               everything for the first time.

            2) If the keys of your new children are no
               longer the same order as the old
               children, then we just render
               everything anew.
               (We may refine this in the future.)

            3) If your key structure remains the same,
               then we update your child nodes on
               a child-by-child basis, and we avoid
               updates where the data had remained
               the same.

        The key to making this all work is that
        `new_dom` should include a `keyed_nodes` option
        where each `keyed_node` has a `key` and supports
        these methods:

            eq - can compare itself to similar nodes
                 for data equality

            render - can create an HTML representation
                     of itself

        The `new_dom` should generally be created with
        something like `vdom.ul`, which will set a
        tag field internally and which will want options
        like `attrs` for attributes.

        For examples of creating vdom objects, look at
        `pm_list_dom.js`.
    */
    function do_full_update() {
        const rendered_dom = exports.render_tag(new_dom);
        replace_content(rendered_dom);
    }

    if (old_dom === undefined) {
        do_full_update();
        return;
    }

    const new_opts = new_dom.opts;
    const old_opts = old_dom.opts;

    if (new_opts.keyed_nodes === undefined) {
        // We generally want to use vdom on lists, and
        // adding keys for childrens lets us avoid unnecessary
        // redraws (or lets us know we should just rebuild
        // the dom).
        blueslip.error("We need keyed_nodes for updates.");
        return;
    }

    const same_structure = exports.eq_array(
        new_opts.keyed_nodes,
        old_opts.keyed_nodes,
        (a, b) => a.key === b.key
    );

    if (!same_structure) {
        /* We could do something smarter like detecting row
           moves, but it's overkill for small lists.
        */
        do_full_update();
        return;
    }

    /*
        DO "QUICK" UPDATES:

        We've gotten this far, so we know we have the
        same overall structure for our parent tag, and
        the only thing left to do with our child nodes
        is to possibly update them in place (via jQuery).
        We will only update nodes whose data has changed.
    */

    const child_elems = find().children();

    _.each(new_opts.keyed_nodes, (new_node, i) => {
        const old_node = old_opts.keyed_nodes[i];
        if (new_node.eq(old_node)) {
            return;
        }
        const rendered_dom = new_node.render();
        child_elems.eq(i).replaceWith(rendered_dom);
    });

    exports.update_attrs(
        find(),
        new_opts.attrs,
        old_opts.attrs
    );
};

exports.update_attrs = (elem, new_attrs, old_attrs) => {
    function make_dict(attrs) {
        const dict = {};
        _.each(attrs, (attr) => {
            const k = attr[0];
            const v = attr[1];
            dict[k] = v;
        });
        return dict;
    }

    const new_dict = make_dict(new_attrs);
    const old_dict = make_dict(old_attrs);

    _.each(new_dict, (v, k) => {
        if (v !== old_dict[k]) {
            elem.attr(k, v);
        }
    });

    _.each(old_dict, (v, k) => {
        if (new_dict[k] === undefined) {
            elem.removeAttr(k);
        }
    });
};

window.vdom = exports;
