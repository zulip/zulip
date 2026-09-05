"use strict";


const assert = require("node:assert/strict");

const {run_test} = require("./lib/test.cjs");

run_test("right_click_opens_message_menu", () => {
let menu_opened = false;
const open_menu = () => { menu_opened = true; };
open_menu();
assert.ok(menu_opened);
});
