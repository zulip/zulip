import $ from "jquery";
import _ from "lodash";

import * as blueslip from "./blueslip";

export type Node<T> = T & {
    key: unknown;
    render: () => string;
    eq: (other: Node<T>) => boolean;
};

type Options<T> = {
    attrs: [string, string][];
    keyed_nodes: Node<T>[];
};

export type Tag<T> = {
    tag_name: string;
    opts: Options<T>;
};

export function eq_array<T>(
    a: T[] | undefined,
    b: T[] | undefined,
    eq: (a_item: T, b_item: T) => boolean,
): boolean {
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

    return a.every((item, i) => eq(item, b[i]));
}

export function ul<T>(opts: Options<T>): Tag<T> {
    return {
        tag_name: "ul",
        opts,
    };
}

export function render_tag<T>(tag: Tag<T>): string {
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
    const attr_str = opts.attrs.map((attr) => ` ${attr[0]}="${_.escape(attr[1])}"`).join("");

    const start_tag = "<" + tag_name + attr_str + ">";
    const end_tag = "</" + tag_name + ">";

    const innards = opts.keyed_nodes.map((node) => node.render()).join("\n");
    return start_tag + "\n" + innards + "\n" + end_tag;
}

export function update_attrs(
    $elem: JQuery,
    new_attrs: Iterable<[string, string]>,
    old_attrs: Iterable<[string, string]>,
): void {
    const new_dict = new Map(new_attrs);
    const old_dict = new Map(old_attrs);

    for (const [k, v] of new_attrs) {
        if (v !== old_dict.get(k)) {
            $elem.attr(k, v);
        }
    }

    for (const [k] of old_attrs) {
        if (!new_dict.has(k)) {
            $elem.removeAttr(k);
        }
    }
}

export function update<T>(
    replace_content: (html: string) => void,
    find: () => JQuery,
    new_dom: Tag<T>,
    old_dom: Tag<T> | undefined,
): void {
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
        `pm_list_dom.ts`.
    */
    function do_full_update(): void {
        const rendered_dom = render_tag(new_dom);
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
        // adding keys for children lets us avoid unnecessary
        // redraws (or lets us know we should just rebuild
        // the dom).
        blueslip.error("We need keyed_nodes for updates.");
        return;
    }

    const same_structure = eq_array(
        new_opts.keyed_nodes,
        old_opts.keyed_nodes,
        (a, b) => a.key === b.key,
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

    const $child_elems = find().children();

    for (const [i, new_node] of new_opts.keyed_nodes.entries()) {
        const old_node = old_opts.keyed_nodes[i];
        if (new_node.eq(old_node)) {
            continue;
        }
        const rendered_dom = new_node.render();
        $child_elems.eq(i).replaceWith($(rendered_dom));
    }

    update_attrs(find(), new_opts.attrs, old_opts.attrs);
}
