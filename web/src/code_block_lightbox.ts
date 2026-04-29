import $ from "jquery";

import render_code_block_lightbox_overlay from "../templates/code_block_lightbox_overlay.hbs";

import * as channel from "./channel.ts";
import {get_unused_fence} from "./fenced_code.ts";
import {$t} from "./i18n.ts";
import * as overlays from "./overlays.ts";

let is_open = false;
let active_code = "";
let active_highlighted_code_html: string | undefined;
let active_language: string | undefined;
let edit_mode = false;
let edit_mode_original_code = "";
let edit_mode_original_highlighted_code_html: string | undefined;
let source_code_element: HTMLElement | undefined;
/** Plain text when the user last entered edit mode (for restoring Pygments HTML if unchanged). */
let plain_text_at_edit_start = "";
/** Highlighted HTML in the lightbox when the user last entered edit mode. */
let lightbox_pygments_html_at_edit_start = "";

function get_current_code(): string {
    if (edit_mode) {
        return (
            $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? ""
        );
    }
    return active_code;
}

function has_unsaved_edits(): boolean {
    if (!edit_mode) {
        return false;
    }
    const editor_code =
        $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
    return editor_code !== active_code;
}

function set_edit_mode(enabled: boolean): void {
    edit_mode = enabled;
    const $overlay = $("#code_block_lightbox_overlay");
    $overlay.toggleClass("code-block-lightbox-edit-mode", edit_mode);
    $overlay.find(".edit-code-in-lightbox").toggleClass("active", edit_mode);
    $overlay
        .find(".edit-code-in-lightbox")
        .attr(
            "aria-label",
            edit_mode ? $t({defaultMessage: "Done editing"}) : $t({defaultMessage: "Edit code"}),
        );
    if (edit_mode) {
<<<<<<< HEAD
        plain_text_at_edit_start = active_code;
        lightbox_pygments_html_at_edit_start =
            $("#code_block_lightbox_overlay code").html() ?? "";
=======
        edit_mode_original_code = active_code;
        edit_mode_original_highlighted_code_html = active_highlighted_code_html;
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
        const $editor = $overlay.find(".code-block-lightbox-editor");
        $editor.val(active_code);
        $editor.trigger("focus");
    }
}

<<<<<<< HEAD
function sync_lightbox_code_view_after_edit(new_plain: string): void {
    active_code = new_plain;
    const $code = $("#code_block_lightbox_overlay code");
    if (new_plain === plain_text_at_edit_start) {
        $code.html(lightbox_pygments_html_at_edit_start);
    } else {
        $code.text(new_plain);
    }
}

function sync_source_code_element_after_save(new_plain: string): void {
    if (source_code_element === undefined) {
        return;
    }
    if (new_plain === plain_text_at_edit_start) {
        $(source_code_element).html(lightbox_pygments_html_at_edit_start);
    } else {
        $(source_code_element).text(new_plain);
    }
=======
function render_highlighted_code_html(code: string, language: string | undefined): Promise<string | undefined> {
    const fence = get_unused_fence(code);
    const language_suffix = language !== undefined && language !== "" ? language : "";
    const markdown_content = `${fence}${language_suffix}\n${code}\n${fence}`;

    return new Promise((resolve) => {
        void channel.post({
            url: "/json/messages/render",
            data: {content: markdown_content},
            success(response_data) {
                const rendered = (response_data as {rendered?: unknown}).rendered;
                if (typeof rendered !== "string") {
                    resolve(undefined);
                    return;
                }
                const wrapper = document.createElement("div");
                wrapper.innerHTML = rendered;
                const highlighted_html = wrapper.querySelector(".codehilite code")?.innerHTML;
                resolve(highlighted_html);
            },
            error() {
                resolve(undefined);
            },
        });
    });
}

function save_edits(): void {
    if (!edit_mode) {
        return;
    }
    const edited_code =
        $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
    const has_changes = edited_code !== edit_mode_original_code;
    active_code = edited_code;
    if (has_changes) {
        $("#code_block_lightbox_overlay code").text(active_code);
        active_highlighted_code_html = undefined;
        if (source_code_element !== undefined) {
            $(source_code_element).text(active_code);
        }
        // Ask backend Markdown renderer for highlighted HTML, then upgrade from plain
        // text to tokenized markup when the response arrives.
        void render_highlighted_code_html(active_code, active_language).then((highlighted_html) => {
            if (highlighted_html === undefined || active_code !== edited_code) {
                return;
            }
            active_highlighted_code_html = highlighted_html;
            $("#code_block_lightbox_overlay code").html(highlighted_html);
            if (source_code_element !== undefined) {
                $(source_code_element).html(highlighted_html);
            }
        });
    } else if (edit_mode_original_highlighted_code_html !== undefined) {
        $("#code_block_lightbox_overlay code").html(edit_mode_original_highlighted_code_html);
        active_highlighted_code_html = edit_mode_original_highlighted_code_html;
    }
    set_edit_mode(false);
}

function discard_edits(): void {
    if (!edit_mode) {
        return;
    }
    active_code = edit_mode_original_code;
    active_highlighted_code_html = edit_mode_original_highlighted_code_html;
    if (edit_mode_original_highlighted_code_html !== undefined) {
        $("#code_block_lightbox_overlay code").html(edit_mode_original_highlighted_code_html);
    } else {
        $("#code_block_lightbox_overlay code").text(active_code);
    }
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val(edit_mode_original_code);
    set_edit_mode(false);
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
}

function close_lightbox(save_changes: boolean): void {
    if (save_changes && edit_mode) {
<<<<<<< HEAD
        const new_plain =
            $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
        sync_lightbox_code_view_after_edit(new_plain);
        sync_source_code_element_after_save(new_plain);
=======
        save_edits();
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
    }
    $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    set_edit_mode(false);
    overlays.close_overlay("code-block-lightbox");
}

function maybe_confirm_close(): void {
    if (!has_unsaved_edits()) {
        close_lightbox(false);
        return;
    }
    $("#code_block_lightbox_overlay").addClass("show-close-prompt");
}

function clear_overlay(): void {
    $("#code_block_lightbox_overlay .code-block-lightbox-title").text("");
    $("#code_block_lightbox_overlay code").text("");
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val("");
    $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    active_code = "";
    active_highlighted_code_html = undefined;
    active_language = undefined;
    edit_mode_original_code = "";
    edit_mode_original_highlighted_code_html = undefined;
    source_code_element = undefined;
    plain_text_at_edit_start = "";
    lightbox_pygments_html_at_edit_start = "";
    set_edit_mode(false);
}

function open_code_block_lightbox(
    language: string | undefined,
<<<<<<< HEAD
=======
    code: string,
    highlighted_code_html: string | undefined,
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
    code_element: HTMLElement | undefined,
): void {
    const code_plain = code_element?.textContent ?? "";
    const code_html = code_element?.innerHTML ?? "";
    const title = language
        ? $t({defaultMessage: "Code Block ({language})"}, {language})
        : $t({defaultMessage: "Code Block"});
    $("#code_block_lightbox_overlay .code-block-lightbox-title").text(title);
<<<<<<< HEAD
    $("#code_block_lightbox_overlay code").html(code_html);
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val(code_plain);
    active_code = code_plain;
=======
    if (highlighted_code_html !== undefined) {
        $("#code_block_lightbox_overlay code").html(highlighted_code_html);
    } else {
        $("#code_block_lightbox_overlay code").text(code);
    }
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val(code);
    active_code = code;
    active_highlighted_code_html = highlighted_code_html;
    active_language = language;
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
    source_code_element = code_element;
    set_edit_mode(false);

    if (is_open) {
        return;
    }

    if (overlays.any_active()) {
        overlays.close_active();
    }

    overlays.open_overlay({
        name: "code-block-lightbox",
        $overlay: $("#code_block_lightbox_overlay"),
        on_close() {
            clear_overlay();
            is_open = false;
        },
    });
    is_open = true;
}

function copy_opener_stylesheets_to_document(target_document: Document): void {
    for (const node of document.querySelectorAll('link[rel="stylesheet"]')) {
        if (!(node instanceof HTMLLinkElement)) {
            continue;
        }
        const link = node;
        if (!link.href) {
            continue;
        }
        let url: URL;
        try {
            url = new URL(link.href);
        } catch {
            continue;
        }
        if (url.origin !== window.location.origin) {
            continue;
        }
        const copy = target_document.createElement("link");
        copy.rel = "stylesheet";
        copy.href = link.href;
        target_document.head.append(copy);
    }
}

function open_code_in_new_tab(): void {
    const code_plain = get_current_code();
    if (code_plain === "") {
        return;
    }

    const popup = window.open("about:blank", "_blank");
    if (popup === null) {
        return;
    }

    const title =
        $("#code_block_lightbox_overlay .code-block-lightbox-title").text() ||
        $t({defaultMessage: "Code block"});
    const use_highlighted = !edit_mode;
    const code_html = $("#code_block_lightbox_overlay code").html() ?? "";

    const doc = popup.document;
    doc.documentElement.lang = document.documentElement.lang;
    doc.documentElement.className = document.documentElement.className;

    const charset_meta = doc.createElement("meta");
    charset_meta.setAttribute("charset", "utf8");
    doc.head.prepend(charset_meta);

    const title_element = doc.createElement("title");
    title_element.textContent = title;
    doc.head.append(title_element);

    copy_opener_stylesheets_to_document(doc);

    doc.body.replaceChildren();

    if (use_highlighted && code_html !== "") {
        const hilite = doc.createElement("div");
        hilite.className = "codehilite";
        const pre = doc.createElement("pre");
        const code_el = doc.createElement("code");
        code_el.innerHTML = code_html;
        pre.append(code_el);
        hilite.append(pre);
        doc.body.append(hilite);
    } else {
        const pre = doc.createElement("pre");
        const code_el = doc.createElement("code");
        code_el.textContent = code_plain;
        pre.append(code_el);
        doc.body.append(pre);
    }

    doc.body.style.margin = "0";

    // Prevent the new tab from retaining a live opener handle.
    popup.opener = null;
}

async function copy_code_in_lightbox(): Promise<void> {
    const code = get_current_code();
    if (code === "") {
        return;
    }

    try {
        await navigator.clipboard.writeText(code);
        return;
    } catch {
        // Fallback for browsers/contexts where clipboard API is unavailable.
    }

    const textarea = document.createElement("textarea");
    textarea.value = code;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
}

export function initialize(): void {
    $("body").append($(render_code_block_lightbox_overlay()));

    $("#main_div, #preview_content, #message-history").on(
        "click",
        ".expand_codeblock, .view_code_block_lightbox",
        function (e) {
            e.preventDefault();
            e.stopPropagation();
            const $codehilite_div = $(this).closest(".codehilite");
            const language = $codehilite_div.attr("data-code-language");
            const $code_element = $codehilite_div.find("code").first();
<<<<<<< HEAD
            open_code_block_lightbox(language, $code_element.get(0));
=======
            const code = $code_element.text();
            const highlighted_code_html = $code_element.html();
            open_code_block_lightbox(language, code, highlighted_code_html, $code_element.get(0));
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
        },
    );

    $("#code_block_lightbox_overlay").on("click", ".open-code-in-new-tab", (e) => {
        e.preventDefault();
        open_code_in_new_tab();
    });

    $("#code_block_lightbox_overlay").on("click", ".copy-code-in-new-tab", (e) => {
        e.preventDefault();
        void copy_code_in_lightbox();
    });

    $("#code_block_lightbox_overlay").on("click", ".edit-code-in-lightbox", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (edit_mode) {
<<<<<<< HEAD
            const new_plain =
                $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ??
                "";
            sync_lightbox_code_view_after_edit(new_plain);
=======
            save_edits();
            return;
>>>>>>> c6ec5157a5 (compose: Add save/discard controls to code lightbox)
        }
        set_edit_mode(true);
    });

    $("#code_block_lightbox_overlay").on("click", ".save-edits-in-lightbox", (e) => {
        e.preventDefault();
        save_edits();
    });

    $("#code_block_lightbox_overlay").on("click", ".discard-edits-in-lightbox", (e) => {
        e.preventDefault();
        discard_edits();
    });

    $("#code_block_lightbox_overlay").on("click", ".exit", (e) => {
        e.preventDefault();
        e.stopPropagation();
        maybe_confirm_close();
    });

    $("#code_block_lightbox_overlay").on("click", ".prompt-save", (e) => {
        e.preventDefault();
        close_lightbox(true);
    });

    $("#code_block_lightbox_overlay").on("click", ".prompt-discard", (e) => {
        e.preventDefault();
        close_lightbox(false);
    });

    $("#code_block_lightbox_overlay").on("click", ".prompt-cancel", (e) => {
        e.preventDefault();
        $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    });

    $("#code_block_lightbox_overlay").on("click", (e) => {
        if ($(e.target).is("#code_block_lightbox_overlay")) {
            e.preventDefault();
            e.stopPropagation();
            maybe_confirm_close();
        }
    });
}
