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

function code_block_line_count(code: string): number {
    return code.trimEnd().split("\n").length;
}

function fill_code_block_lightbox_gutters(code: string): void {
    const line_count = code_block_line_count(code);
    const $gutters = $("#code_block_lightbox_overlay .code-block-lightbox-gutter");
    for (const gutter of $gutters) {
        const $gutter = $(gutter).empty();
        for (let i = 1; i <= line_count; i += 1) {
            $gutter.append($("<span>").text(String(i)));
        }
    }
}

function bind_mutual_vertical_scroll($a: JQuery, $b: JQuery): void {
    let syncing = false;
    function attach(from: JQuery, to: JQuery): void {
        from.on("scroll.code_block_lightbox_sync", () => {
            if (syncing) {
                return;
            }
            syncing = true;
            to.prop("scrollTop", from.prop("scrollTop") as number);
            syncing = false;
        });
    }
    attach($a, $b);
    attach($b, $a);
}

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
        edit_mode_original_code = active_code;
        edit_mode_original_highlighted_code_html = active_highlighted_code_html;
        const $editor = $overlay.find(".code-block-lightbox-editor");
        $editor.val(active_code);
        fill_code_block_lightbox_gutters(active_code);
        $editor.trigger("focus");
    }
}

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
        fill_code_block_lightbox_gutters(active_code);
        if (source_code_element !== undefined) {
            $(source_code_element).text(active_code);
        }
        void render_highlighted_code_html(active_code, active_language).then((highlighted_html) => {
            if (highlighted_html === undefined || active_code !== edited_code) {
                return;
            }
            active_highlighted_code_html = highlighted_html;
            $("#code_block_lightbox_overlay code").html(highlighted_html);
            fill_code_block_lightbox_gutters(active_code);
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
    fill_code_block_lightbox_gutters(active_code);
    set_edit_mode(false);
}

function close_lightbox(save_changes: boolean): void {
    if (save_changes && edit_mode) {
        save_edits();
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
    fill_code_block_lightbox_gutters("");
    $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    active_code = "";
    active_highlighted_code_html = undefined;
    active_language = undefined;
    edit_mode_original_code = "";
    edit_mode_original_highlighted_code_html = undefined;
    source_code_element = undefined;
    set_edit_mode(false);
}

function open_code_block_lightbox(
    language: string | undefined,
    code: string,
    highlighted_code_html: string | undefined,
    code_element: HTMLElement | undefined,
): void {
    const title = language
        ? $t({defaultMessage: "Code Block ({language})"}, {language})
        : $t({defaultMessage: "Code Block"});
    $("#code_block_lightbox_overlay .code-block-lightbox-title").text(title);
    if (highlighted_code_html !== undefined) {
        $("#code_block_lightbox_overlay code").html(highlighted_code_html);
    } else {
        $("#code_block_lightbox_overlay code").text(code);
    }
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val(code);
    active_code = code;
    active_highlighted_code_html = highlighted_code_html;
    active_language = language;
    source_code_element = code_element;
    set_edit_mode(false);
    fill_code_block_lightbox_gutters(code);

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

const OPEN_TAB_WRAP_CLASS = "code-block-lightbox-open-tab-wrap";
const OPEN_TAB_GUTTER_CLASS = "code-block-lightbox-open-tab-gutter";

function append_open_tab_document_styles(doc: Document): void {
    const style = doc.createElement("style");
    const wrap = `.${OPEN_TAB_WRAP_CLASS}`;
    const gutter = `.${OPEN_TAB_GUTTER_CLASS}`;
    style.textContent = `
${wrap} {
    display: flex;
    flex-direction: row;
    align-items: stretch;
    min-height: 100vh;
    box-sizing: border-box;
}
${wrap} ${gutter} {
    box-sizing: border-box;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    min-width: 2.5em;
    padding: 10px 0.6em 10px 0.8em;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
    text-align: right;
    user-select: none;
    font-size: 0.9em;
    line-height: 1.4;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    color: hsl(0deg 0% 50%);
    border-right: 1px solid var(--color-markdown-pre-border, hsl(0deg 0% 80%));
    background-color: var(--color-markdown-pre-background, hsl(0deg 0% 96%));
}
${wrap} ${gutter}::-webkit-scrollbar {
    display: none;
    width: 0;
    height: 0;
}
${wrap} ${gutter} span {
    display: block;
}
:root.dark-theme ${wrap} ${gutter} {
    color: hsl(0deg 0% 62%);
}
${wrap} > .codehilite {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    margin: 0;
}
${wrap} > .codehilite pre,
${wrap} > pre {
    flex: 1;
    min-width: 0;
    min-height: 0;
    margin: 0;
    padding: 10px 12px;
    overflow: auto;
    font-size: 0.9em;
    line-height: 1.4;
    white-space: pre;
    border: 0;
    border-radius: 0;
}
`;
    doc.head.append(style);
}

function create_open_tab_gutter(doc: Document, code: string): HTMLElement {
    const gutter = doc.createElement("div");
    gutter.className = OPEN_TAB_GUTTER_CLASS;
    gutter.setAttribute("aria-hidden", "true");
    const line_count = code_block_line_count(code);
    for (let i = 1; i <= line_count; i += 1) {
        const span = doc.createElement("span");
        span.textContent = String(i);
        gutter.append(span);
    }
    return gutter;
}

function append_open_tab_scroll_sync_script(doc: Document): void {
    const script = doc.createElement("script");
    const g_sel = JSON.stringify(`.${OPEN_TAB_GUTTER_CLASS}`);
    const w_sel = JSON.stringify(`.${OPEN_TAB_WRAP_CLASS}`);
    script.textContent = `(function(){var g=document.querySelector(${g_sel});var w=document.querySelector(${w_sel});if(!g||!w)return;var p=w.querySelector("pre");if(!p)return;var s=false;function b(a,t){a.addEventListener("scroll",function(){if(s)return;s=true;t.scrollTop=a.scrollTop;s=false;});}b(g,p);b(p,g);})();`;
    doc.body.append(script);
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
    append_open_tab_document_styles(doc);

    const wrap = doc.createElement("div");
    wrap.className = OPEN_TAB_WRAP_CLASS;
    wrap.append(create_open_tab_gutter(doc, code_plain));

    if (use_highlighted && code_html !== "") {
        const hilite = doc.createElement("div");
        hilite.className = "codehilite";
        const pre = doc.createElement("pre");
        const code_el = doc.createElement("code");
        code_el.innerHTML = code_html;
        pre.append(code_el);
        hilite.append(pre);
        wrap.append(hilite);
    } else {
        const pre = doc.createElement("pre");
        const code_el = doc.createElement("code");
        code_el.textContent = code_plain;
        pre.append(code_el);
        wrap.append(pre);
    }

    doc.body.append(wrap);
    append_open_tab_scroll_sync_script(doc);

    doc.body.style.margin = "0";

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
            const code = $code_element.text();
            const highlighted_code_html = $code_element.html();
            open_code_block_lightbox(language, code, highlighted_code_html, $code_element.get(0));
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
            save_edits();
            return;
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

    const $overlay = $("#code_block_lightbox_overlay");
    bind_mutual_vertical_scroll(
        $overlay.find(".code-block-lightbox-scroll-area pre"),
        $overlay.find(".code-block-lightbox-scroll-area .code-block-lightbox-gutter"),
    );
    bind_mutual_vertical_scroll(
        $overlay.find(".code-block-lightbox-editor"),
        $overlay.find(".code-block-lightbox-edit-row .code-block-lightbox-gutter"),
    );

    $overlay.on("input", ".code-block-lightbox-editor", () => {
        fill_code_block_lightbox_gutters(get_current_code());
    });
}
