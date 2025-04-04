import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_add_saved_snippet_modal from "../templates/add_saved_snippet_modal.hbs";
import render_confirm_delete_saved_snippet from "../templates/confirm_dialog/confirm_delete_saved_snippet.hbs";
import render_edit_saved_snippet_modal from "../templates/edit_saved_snippet_modal.hbs";

import * as channel from "./channel.ts";
import * as compose_ui from "./compose_ui.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as rows from "./rows.ts";
import * as saved_snippets from "./saved_snippets.ts";

let saved_snippets_widget: dropdown_widget.DropdownWidget | undefined;
let saved_snippets_dropdown: tippy.Instance | undefined;
let composebox_saved_snippets_dropdown_widget = false;

function submit_create_saved_snippet_form(): void {
    const title = $<HTMLInputElement>("#add-new-saved-snippet-modal .saved-snippet-title")
        .val()
        ?.trim();
    const content = $<HTMLInputElement>("#add-new-saved-snippet-modal .saved-snippet-content")
        .val()
        ?.trim();

    assert(title && content);

    dialog_widget.submit_api_request(channel.post, "/json/saved_snippets", {title, content});
}

function submit_edit_saved_snippet_form(saved_snippet_id: number): void {
    const title = $<HTMLInputElement>("#edit-saved-snippet-modal .saved-snippet-title")
        .val()
        ?.trim();
    const content = $<HTMLInputElement>("#edit-saved-snippet-modal .saved-snippet-content")
        .val()
        ?.trim();

    assert(title && content);

    dialog_widget.submit_api_request(channel.patch, `/json/saved_snippets/${saved_snippet_id}`, {
        title,
        content,
    });
}

function update_submit_button_state(): void {
    const title = $<HTMLInputElement>("#add-new-saved-snippet-modal .saved-snippet-title")
        .val()
        ?.trim();
    const content = $<HTMLInputElement>("#add-new-saved-snippet-modal .saved-snippet-content")
        .val()
        ?.trim();
    const $submit_button = $("#add-new-saved-snippet-modal .dialog_submit_button");

    $submit_button.prop("disabled", true);
    if (title && content) {
        $submit_button.prop("disabled", false);
    }
}

function saved_snippet_modal_post_render(): void {
    $("#add-new-saved-snippet-modal").on("input", "input,textarea", update_submit_button_state);
}

function saved_snippet_edit_modal_post_render(saved_snippet: saved_snippets.SavedSnippet): void {
    $("#edit-saved-snippet-modal").on("input", "input,textarea", () => {
        const title = $<HTMLInputElement>("#edit-saved-snippet-modal .saved-snippet-title")
            .val()
            ?.trim();
        const content = $<HTMLInputElement>("#edit-saved-snippet-modal .saved-snippet-content")
            .val()
            ?.trim();
        const $submit_button = $("#edit-saved-snippet-modal .dialog_submit_button");

        $submit_button.prop("disabled", true);
        if (title === saved_snippet.title && content === saved_snippet.content) {
            return;
        }
        if (title && content) {
            $submit_button.prop("disabled", false);
        }
    });
}

export function rerender_dropdown_widget(): void {
    if (saved_snippets_widget && saved_snippets_dropdown) {
        const options = saved_snippets.get_options_for_dropdown_widget();
        saved_snippets_widget.list_widget?.replace_list_data(options);
        saved_snippets_widget.show_empty_if_no_items($(saved_snippets_dropdown.popper));
    }
}

function delete_saved_snippet(saved_snippet_id: string): void {
    void channel.del({
        url: "/json/saved_snippets/" + saved_snippet_id,
    });
}

function item_click_callback(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
    is_sticky_bottom_option_clicked: boolean,
): void {
    event.preventDefault();
    event.stopPropagation();

    if (
        $(event.target).closest(".saved_snippets-dropdown-list-container .dropdown-list-delete")
            .length > 0
    ) {
        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete saved snippet?"}),
            html_body: render_confirm_delete_saved_snippet(),
            on_click() {
                const saved_snippet_id = $(event.currentTarget).attr("data-unique-id");
                assert(saved_snippet_id !== undefined);
                delete_saved_snippet(saved_snippet_id);
            },
        });
        return;
    }

    if (
        $(event.target).closest(".saved_snippets-dropdown-list-container .dropdown-list-edit")
            .length > 0
    ) {
        const saved_snippet_id = $(event.currentTarget).attr("data-unique-id");
        assert(saved_snippet_id !== undefined);

        const saved_snippet = saved_snippets.get_saved_snippet_by_id(
            Number.parseInt(saved_snippet_id, 10),
        );
        assert(saved_snippet !== undefined);
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Edit saved snippet"}),
            html_body: render_edit_saved_snippet_modal({
                title: saved_snippet.title,
                content: saved_snippet.content,
            }),
            html_submit_button: $t_html({defaultMessage: "Save"}),
            id: "edit-saved-snippet-modal",
            form_id: "edit-saved-snippet-form",
            update_submit_disabled_state_on_change: true,
            on_click() {
                submit_edit_saved_snippet_form(saved_snippet.id);
            },
            on_shown: () => $("#edit-saved-snippet-title").trigger("focus"),
            post_render() {
                saved_snippet_edit_modal_post_render(saved_snippet);
            },
        });
        return;
    }

    dropdown.hide();
    // Get target textarea where the "Add saved snippet" button is clicked.
    const $target_element = $(dropdown.reference);
    let $target_textarea: JQuery<HTMLTextAreaElement>;
    let edit_message_id: string | undefined;
    if ($target_element.parents(".message_edit_form").length === 1) {
        edit_message_id = rows.id($target_element.parents(".message_row")).toString();
        $target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
    } else {
        $target_textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
    }
    if (is_sticky_bottom_option_clicked) {
        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Create a new saved snippet"}),
            html_body: render_add_saved_snippet_modal({
                prepopulated_content: $target_textarea.val(),
            }),
            html_submit_button: $t_html({defaultMessage: "Save"}),
            id: "add-new-saved-snippet-modal",
            form_id: "add-new-saved-snippet-form",
            update_submit_disabled_state_on_change: true,
            on_click: submit_create_saved_snippet_form,
            on_shown: () => $("#new-saved-snippet-title").trigger("focus"),
            post_render: saved_snippet_modal_post_render,
        });
    } else {
        const current_value = widget.current_value;
        assert(typeof current_value === "number");
        const saved_snippet = saved_snippets.get_saved_snippet_by_id(current_value);
        assert(saved_snippet !== undefined);
        const content = saved_snippet.content;
        compose_ui.insert_syntax_and_focus(content, $target_textarea);
    }
}

export function setup_saved_snippets_dropdown_widget(widget_selector: string): void {
    new dropdown_widget.DropdownWidget({
        widget_name: "saved_snippets",
        widget_selector,
        get_options: saved_snippets.get_options_for_dropdown_widget,
        item_click_callback,
        $events_container: $("body"),
        unique_id_type: "number",
        sticky_bottom_option: $t({
            defaultMessage: "Create a new saved snippet",
        }),
        on_show_callback(dropdown: tippy.Instance, widget: dropdown_widget.DropdownWidget) {
            saved_snippets_widget = widget;
            saved_snippets_dropdown = dropdown;
        },
        focus_target_on_hidden: false,
        prefer_top_start_placement: true,
        tippy_props: {
            // Using -100 as x offset makes saved snippet icon be in the center
            // of the dropdown widget and 5 as y offset is what we use in compose
            // recipient dropdown widget.
            offset: [-100, 5],
        },
    }).setup();
}

export function setup_saved_snippets_dropdown_widget_if_needed(): void {
    if (!composebox_saved_snippets_dropdown_widget) {
        composebox_saved_snippets_dropdown_widget = true;
        setup_saved_snippets_dropdown_widget(".saved-snippets-composebox-widget");
    }
}
