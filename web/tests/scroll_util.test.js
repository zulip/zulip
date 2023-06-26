"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const scroll_util = zrequire("scroll_util");

run_test("scroll_delta", () => {
    // If we are entirely on-screen, don't scroll
    assert.equal(
        0,
        scroll_util.scroll_delta({
            elem_top: 1,
            elem_bottom: 9,
            container_height: 10,
        }),
    );

    assert.equal(
        0,
        scroll_util.scroll_delta({
            elem_top: -5,
            elem_bottom: 15,
            container_height: 10,
        }),
    );

    // The top is offscreen.
    assert.equal(
        -3,
        scroll_util.scroll_delta({
            elem_top: -3,
            elem_bottom: 5,
            container_height: 10,
        }),
    );

    assert.equal(
        -3,
        scroll_util.scroll_delta({
            elem_top: -3,
            elem_bottom: -1,
            container_height: 10,
        }),
    );

    assert.equal(
        -11,
        scroll_util.scroll_delta({
            elem_top: -150,
            elem_bottom: -1,
            container_height: 10,
        }),
    );

    // The bottom is offscreen.
    assert.equal(
        3,
        scroll_util.scroll_delta({
            elem_top: 7,
            elem_bottom: 13,
            container_height: 10,
        }),
    );

    assert.equal(
        3,
        scroll_util.scroll_delta({
            elem_top: 11,
            elem_bottom: 13,
            container_height: 10,
        }),
    );

    assert.equal(
        11,
        scroll_util.scroll_delta({
            elem_top: 11,
            elem_bottom: 99,
            container_height: 10,
        }),
    );
});

run_test("scroll_element_into_container", () => {
    const $container = (function () {
        let top = 3;
        return {
            height: () => 100,
            scrollTop: (arg) => {
                if (arg === undefined) {
                    return top;
                }
                top = arg;
                return this;
            },
            __zjquery: true,
        };
    })();

    const $elem1 = {
        innerHeight: () => 25,
        position: () => ({
            top: 0,
        }),
    };
    scroll_util.scroll_element_into_container($elem1, $container);
    assert.equal($container.scrollTop(), 3);

    const $elem2 = {
        innerHeight: () => 15,
        position: () => ({
            top: 250,
        }),
    };
    scroll_util.scroll_element_into_container($elem2, $container);
    assert.equal($container.scrollTop(), 250 - 100 + 3 + 15);
});
