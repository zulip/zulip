set_global('blueslip', global.make_zblueslip());
zrequire('util');
zrequire('vdom');

run_test('basics', () => {
    const opts = {
        keyed_nodes: [],
        attrs: [
            ['class', 'foo'],
            ['title', 'cats & <"dogs">'],
        ],
    };

    const ul = vdom.ul(opts);

    const html = vdom.render_tag(ul);

    assert.equal(
        html,
        '<ul class="foo" title="cats &amp; &lt;&quot;dogs&quot;&gt;">\n\n' +
        '</ul>'
    );
});

function make_child(i, name) {
    const render = () => {
        return '<li>' + name + '</li>';
    };

    const eq = (other) => {
        return name === other.name;
    };

    return {
        key: i,
        render: render,
        name: name,
        eq: eq,
    };
}

function make_children(lst) {
    return _.map(lst, (i) => {
        return make_child(i, 'foo' + i);
    });
}

run_test('children', () => {
    let rendered_html;

    const container = {
        html: (html) => {
            rendered_html = html;
        },
    };

    const nodes = make_children([1, 2, 3]);

    const opts = {
        keyed_nodes: nodes,
        attrs: [],
    };

    const ul = vdom.ul(opts);

    vdom.update(container, ul);

    assert.equal(
        rendered_html,
        '<ul>\n' +
        '<li>foo1</li>\n' +
        '<li>foo2</li>\n' +
        '<li>foo3</li>\n' +
        '</ul>'
    );

    // Force a complete redraw.
    const new_nodes = make_children([4, 5]);
    const new_opts = {
        keyed_nodes: new_nodes,
        attrs: [
            ['class', 'main'],
        ],
    };

    const new_ul = vdom.ul(new_opts);
    vdom.update(container, new_ul, ul);

    assert.equal(
        rendered_html,
        '<ul class="main">\n' +
        '<li>foo4</li>\n' +
        '<li>foo5</li>\n' +
        '</ul>'
    );
});

run_test('partial updates', () => {
    let rendered_html;

    const container = {
        html: (html) => {
            rendered_html = html;
        },
    };

    const nodes = make_children([1, 2, 3]);

    const opts = {
        keyed_nodes: nodes,
        attrs: [],
    };

    const ul = vdom.ul(opts);

    vdom.update(container, ul);

    assert.equal(
        rendered_html,
        '<ul>\n' +
        '<li>foo1</li>\n' +
        '<li>foo2</li>\n' +
        '<li>foo3</li>\n' +
        '</ul>'
    );

    container.html = () => {
        throw Error('should not replace entire html');
    };

    let patched_html;

    container.find = (tag_name) => {
        assert.equal(tag_name, 'ul');
        return {
            children: () => {
                return {
                    eq: (i) => {
                        assert.equal(i, 0);
                        return {
                            replaceWith: (html) => {
                                patched_html = html;
                            },
                        };
                    },
                };
            },
        };
    };

    const new_nodes = make_children([1, 2, 3]);
    new_nodes[0] = make_child(1, 'modified1');

    const new_opts = {
        keyed_nodes: new_nodes,
        attrs: [],
    };

    const new_ul = vdom.ul(new_opts);
    vdom.update(container, new_ul, ul);

    assert.equal(patched_html, '<li>modified1</li>');
});

run_test('eq_array easy cases', () => {
    const bogus_eq = () => {
        throw Error('we should not be comparing elements');
    };

    assert.equal(
        vdom.eq_array(undefined, undefined, bogus_eq),
        true);

    const x = [1, 2, 3];
    assert.equal(
        vdom.eq_array(x, undefined, bogus_eq),
        false);

    assert.equal(
        vdom.eq_array(undefined, x, bogus_eq),
        false);

    assert.equal(vdom.eq_array(x, x, bogus_eq), true);

    // length check should also short-circuit
    const y = [1, 2, 3, 4, 5];
    assert.equal(vdom.eq_array(x, y, bogus_eq), false);

    // same length, same values, but different order
    const eq = (a, b) => a === b;
    const z = [3, 2, 1];
    assert.equal(vdom.eq_array(x, z, eq), false);
});

run_test('eq_array elementwise', () => {
    const a = [51, 32, 93];
    const b = [31, 52, 43];
    const eq = (a, b) => a % 10 === b % 10;
    assert.equal(vdom.eq_array(a, b, eq), true);
});

run_test('error checking', () => {
    blueslip.set_test_data(
        'error',
        'We need keyed_nodes for updates.');

    const container = 'whatever';
    const ul = {opts: {}};

    vdom.update(container, ul, ul);
    assert.equal(blueslip.get_test_logs('error').length, 1);

    blueslip.set_test_data(
        'error',
        'We need keyed_nodes to render innards.');
    vdom.render_tag(ul);

});
