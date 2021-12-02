"use strict";

const {strict: assert} = require("assert");

const {buddy_list} = require("../../static/js/buddy_list");
const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

mock_esm("../../static/js/ui", {
    get_scroll_element: (element) => element,
});

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

run_test("scroll_element_into_container_for_buddy_list", () => {
    const container = (function () {
        let top = 3;
        return {
            scrollTop: (arg) => {
                if (arg === undefined) {
                    return top;
                }
                top = arg;
                return this;
            },
            height: () => 100,
            offset: () => ({
                top: 0,
            }),
        };
    })();

    $("#users_heading")[0] = {
        getBoundingClientRect: () => ({}),
    };

    $("#users_heading").innerHeight = () => 25;

    buddy_list.other_keys = [1, 2, 3];

    $("#others_heading")[0] = {
        getBoundingClientRect: () => ({}),
    };

    $("#others_heading").innerHeight = () => 25;

    let called = false;
    const elem1 = {
        innerHeight: () => 25,
        offset: () => ({
            top: 0,
        }),
        0: {
            getBoundingClientRect: () => ({}),
            scrollIntoView: () => {
                /* istanbul ignore next */
                called = true;
            },
        },
        expectOne() {
            return elem1;
        },
        attr: (tag) => {
            assert.ok(tag === "data-user-id");
            return 1;
        },
    };
    scroll_util.scroll_element_into_container_for_buddy_list(elem1, container);
    assert.ok(!called);

    const elem2 = {
        innerHeight: () => 25,
        offset: () => ({
            top: -10,
        }),
        0: {
            getBoundingClientRect: () => ({}),
            scrollIntoView: (align_to_top) => {
                const expected_align_to_top = true;
                assert.equal(align_to_top, expected_align_to_top);
                return this;
            },
        },
        expectOne() {
            return elem2;
        },
        attr: (tag) => {
            assert.ok(tag === "data-user-id");
            return 2;
        },
    };
    scroll_util.scroll_element_into_container_for_buddy_list(elem2, container);

    const elem3 = {
        innerHeight: () => 15,
        offset: () => ({
            top: 250,
        }),
        0: {
            getBoundingClientRect: () => ({}),
            scrollIntoView: (align_to_top) => {
                const expected_align_to_top = false;
                assert.equal(align_to_top, expected_align_to_top);
            },
        },
        expectOne() {
            return elem3;
        },
        attr: (tag) => {
            assert.ok(tag === "data-user-id");
            return 3;
        },
    };
    scroll_util.scroll_element_into_container_for_buddy_list(elem3, container);
});
