import $ from "jquery";
import assert from "minimalistic-assert";

import * as compose_ui from "./compose_ui.ts";
import * as rows from "./rows.ts";

export class ComposeIconSession {
    is_editing_existing_message: boolean;
    private edit_message_id: number | undefined;

    constructor(compose_icon: HTMLElement) {
        if ($(compose_icon).parents(".message_edit_form").length === 1) {
            this.edit_message_id = rows.id($(compose_icon).parents(".message_row"));
            this.is_editing_existing_message = true;
        } else {
            this.is_editing_existing_message = false;
        }
    }

    compose_textarea(): JQuery<HTMLTextAreaElement> {
        assert(!this.is_editing_existing_message);
        return $<HTMLTextAreaElement>("textarea#compose-textarea");
    }

    edit_textarea(): JQuery<HTMLTextAreaElement> {
        assert(this.edit_message_id !== undefined);
        return $(`#edit_form_${CSS.escape(`${this.edit_message_id}`)} .message_edit_content`);
    }

    textarea(): JQuery<HTMLTextAreaElement> {
        if (this.is_editing_existing_message) {
            return this.edit_textarea();
        }
        return this.compose_textarea();
    }

    insert_inline_markdown_into_textarea(syntax: string): void {
        const $textarea = this.textarea();
        $textarea.trigger("focus");
        compose_ui.smart_insert_inline($textarea, syntax);
    }

    insert_block_markdown_into_textarea(syntax: string, padding_newlines: number): void {
        const $textarea = this.textarea();
        $textarea.trigger("focus");
        compose_ui.smart_insert_block($textarea, syntax, padding_newlines);
    }

    focus_on_edit_textarea(): void {
        assert(this.edit_message_id !== undefined);
        this.edit_textarea().trigger("focus");
    }
}
