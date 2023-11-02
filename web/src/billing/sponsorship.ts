import $ from "jquery";

import * as helpers from "./helpers";

export function initialize(): void {
    helpers.set_sponsorship_form();
}

$(() => {
    initialize();
});
