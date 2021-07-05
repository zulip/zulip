import $ from "jquery";

import render_edit_fields_modal from "../templates/settings/edit_fields_modal.hbs";

import * as blueslip from "./blueslip";
import * as overlays from "./overlays";

/*
    Look for edit_fields_modal in settings_users.js to see an
    example of how to use this widget.

    Some things to note:

        1) We create the DOM elements on the fly, and we remove the
           DOM elements once it's closed.

        2) We attach the DOM elements for the modal to modal_fields.parent.

        3) The cancel button is driven by bootstrap.js.

        4) We do not handle closing the modal on clicking "Save
           changes" here, because some modals show errors, if the
           request fails, in the modal itself without closing.

        5) If a caller needs to run code after the modal body is added
           to DOM, it can do so by passing a post_render hook.
*/

export function launch(modal_fields) {
    const required_modal_fields = ["html_heading", "parent", "html_body", "on_click"];

    for (const field of required_modal_fields) {
        if (!modal_fields[field]) {
            blueslip.error("programmer omitted " + field);
        }
    }

    const html = render_edit_fields_modal({
        html_heading: modal_fields.html_heading,
    });
    const edit_fields_modal = $(html);
    modal_fields.parent.append(edit_fields_modal);

    if (overlays.is_modal_open()) {
        overlays.close_modal("#edit-fields-modal");
    }

    edit_fields_modal.find(".edit-fields-modal-body").append(modal_fields.html_body);

    if (modal_fields.post_render !== undefined) {
        modal_fields.post_render();
    }

    // Set up handlers.
    $(".submit-modal-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        modal_fields.on_click();
    });

    edit_fields_modal.on("hidden.bs.modal", () => {
        edit_fields_modal.remove();
    });

    // Open the modal
    overlays.open_modal("#edit-fields-modal");
}
