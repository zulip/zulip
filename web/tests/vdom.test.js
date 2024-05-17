"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");

const vdom = zrequire("vdom");

run_test("basics", () => {
    const opts = {
        keyed_nodes: [],
        attrs: [
            ["class", "foo"],
            ["title", 'cats & <"dogs">'],
        ],
    };

    const ul = vdom.ul(opts);

    const html = vdom.render_tag(ul);

    assert.equal(html, '<ul class="foo" title="cats &amp; &lt;&quot;dogs&quot;&gt;">\n\n</ul>');
});

run_test("attribute escaping", () => {
    // So far most of the time our attributes are
    // hard-coded classes like "dm-list",
    // but we need to be defensive about future code
    // that might use data from possibly malicious users.
    const opts = {
        keyed_nodes: [],
        attrs: [
            ["class", '">something evil<div class="'],
            ["title", "apples & oranges"],
        ],
    };

    const ul = vdom.ul(opts);

    const html = vdom.render_tag(ul);

    assert.equal(
        html,
        '<ul class="&quot;&gt;something evil&lt;div class=&quot;" ' +
            'title="apples &amp; oranges">\n\n</ul>',
    );
});

run_test("attribute updates", () => {
    const opts = {
        keyed_nodes: [],
        attrs: [
            ["class", "same"],
            ["color", "blue"],
            ["id", "101"],
        ],
    };

    const ul = vdom.ul(opts);

    const html = vdom.render_tag(ul);

    assert.equal(html, '<ul class="same" color="blue" id="101">\n\n</ul>');

    let updated;
    let removed;

    function find() {
        return {
            children: () => [],

            attr(k, v) {
                assert.equal(k, "color");
                assert.equal(v, "red");
                updated = true;
            },

            removeAttr(k) {
                assert.equal(k, "id");
                removed = true;
            },
        };
    }

    const new_opts = {
        keyed_nodes: [],
        attrs: [
            ["class", "same"], // unchanged
            ["color", "red"],
        ],
    };

    const new_ul = vdom.ul(new_opts);
    const replace_content = undefined;

    vdom.update(replace_content, find, new_ul, ul);

    assert.ok(updated);
    assert.ok(removed);
});

function make_child(i, name) {
    const render = () => "<li>" + name + "</li>";

    const eq = (other) => name === other.name;

    return {
        key: i,
        render,
        name,
        eq,
    };
}

function make_children(lst) {
    return lst.map((i) => make_child(i, "foo" + i));
}

run_test("children", () => {
    let rendered_html;

    function replace_content(html) {
        rendered_html = html;
    }

    const find = undefined;

    const nodes = make_children([1, 2, 3]);

    const opts = {
        keyed_nodes: nodes,
        attrs: [],
    };

    const ul = vdom.ul(opts);

    vdom.update(replace_content, find, ul);

    assert.equal(rendered_html, "<ul>\n<li>foo1</li>\n<li>foo2</li>\n<li>foo3</li>\n</ul>");

    // Force a complete redraw.
    const new_nodes = make_children([4, 5]);
    const new_opts = {
        keyed_nodes: new_nodes,
        attrs: [["class", "main"]],
    };

    const new_ul = vdom.ul(new_opts);
    vdom.update(replace_content, find, new_ul, ul);

    assert.equal(rendered_html, '<ul class="main">\n<li>foo4</li>\n<li>foo5</li>\n</ul>');
});

run_test("partial updates", () => {
    let rendered_html;

    let replace_content = (html) => {
        rendered_html = html;
    };

    let find;

    const nodes = make_children([1, 2, 3]);

    const opts = {
        keyed_nodes: nodes,
        attrs: [],
    };

    const ul = vdom.ul(opts);

    vdom.update(replace_content, find, ul);

    assert.equal(rendered_html, "<ul>\n<li>foo1</li>\n<li>foo2</li>\n<li>foo3</li>\n</ul>");

    /* istanbul ignore next */
    replace_content = () => {
        throw new Error("should not replace entire html");
    };

    let $patched;

    find = () => ({
        children: () => ({
            eq(i) {
                assert.equal(i, 0);
                return {
                    replaceWith($element) {
                        $patched = $element;
                    },
                };
            },
        }),
    });

    const new_nodes = make_children([1, 2, 3]);
    new_nodes[0] = make_child(1, "modified1");

    const new_opts = {
        keyed_nodes: new_nodes,
        attrs: [],
    };

    const new_ul = vdom.ul(new_opts);
    vdom.update(replace_content, find, new_ul, ul);

    assert.equal($patched.selector, "<li>modified1</li>");
});

run_test("eq_array easy cases", () => {
    /* istanbul ignore next */
    const bogus_eq = () => {
        throw new Error("we should not be comparing elements");
    };

    assert.equal(vdom.eq_array(undefined, undefined, bogus_eq), true);

    const x = [1, 2, 3];
    assert.equal(vdom.eq_array(x, undefined, bogus_eq), false);

    assert.equal(vdom.eq_array(undefined, x, bogus_eq), false);

    assert.equal(vdom.eq_array(x, x, bogus_eq), true);

    // length check should also short-circuit
    const y = [1, 2, 3, 4, 5];
    assert.equal(vdom.eq_array(x, y, bogus_eq), false);

    // same length, same values, but different order
    const eq = (a, b) => a === b;
    const z = [3, 2, 1];
    assert.equal(vdom.eq_array(x, z, eq), false);
});

run_test("eq_array element-wise", () => {
    const a = [51, 32, 93];
    const b = [31, 52, 43];
    const eq = (a, b) => a % 10 === b % 10;
    assert.equal(vdom.eq_array(a, b, eq), true);
});

run_test("error checking", () => {
    blueslip.expect("error", "We need keyed_nodes for updates.");

    const replace_content = "whatever";
    const find = "whatever";
    const ul = {opts: {attrs: []}};

    vdom.update(replace_content, find, ul, ul);
});
