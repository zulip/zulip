import $ from "jquery";

import * as browser_history from "./browser_history";
import {page_params} from "./page_params";
import * as search_pill from "./search_pill";

export let widget;

export function initialize() {
    if (!page_params.search_pills_enabled) {
        return;
    }
    const container = $("#search_arrows");
    widget = search_pill.create_pills(container);

    widget.onPillRemove(() => {
        if (widget.items().length === 0) {
            browser_history.go_to_location("");
        }
    });

    widget.createPillonPaste(() => false);
}
