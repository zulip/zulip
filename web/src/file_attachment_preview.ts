import hljs from "highlight.js/lib/common";
import matlab from "highlight.js/lib/languages/matlab";
import $ from "jquery";

import render_file_attachment_preview from "../templates/file_attachment_preview.hbs";

import * as attachment_navigator from "./attachment_navigator.ts";
import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";
import {message_render_response_schema} from "./message_store.ts";
import * as overlays from "./overlays.ts";
import {user_settings} from "./user_settings.ts";

hljs.registerLanguage("matlab", matlab);

// Map file extensions to highlight.js language names.
// Extensions not listed here will use highlightAuto().
const EXT_TO_HLJS_LANGUAGE: Record<string, string> = {
    py: "python",
    js: "javascript",
    mjs: "javascript",
    cjs: "javascript",
    ts: "typescript",
    tsx: "typescript",
    jsx: "javascript",
    rb: "ruby",
    rs: "rust",
    go: "go",
    java: "java",
    kt: "kotlin",
    kts: "kotlin",
    c: "c",
    h: "c",
    cpp: "cpp",
    cc: "cpp",
    cxx: "cpp",
    hpp: "cpp",
    hh: "cpp",
    cs: "csharp",
    swift: "swift",
    m: "matlab",
    r: "r",
    pl: "perl",
    pm: "perl",
    php: "php",
    lua: "lua",
    sh: "bash",
    bash: "bash",
    zsh: "bash",
    sql: "sql",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    xml: "xml",
    html: "xml",
    htm: "xml",
    css: "css",
    scss: "scss",
    less: "less",
    makefile: "makefile",
    mk: "makefile",
    diff: "diff",
    patch: "diff",
    ini: "ini",
    toml: "ini",
    cfg: "ini",
    graphql: "graphql",
    gql: "graphql",
    vb: "vbnet",
    wasm: "wasm",
    objc: "objectivec",
};

// Built-in set of extensions that are always previewable.
// Includes txt, md, csv, pdf, plus all extensions with known syntax highlighting.
const BUILT_IN_PREVIEW_EXTENSIONS = new Set([
    "txt",
    "md",
    "csv",
    "pdf",
    ...Object.keys(EXT_TO_HLJS_LANGUAGE),
]);

const MAX_PREVIEW_SIZE = 256 * 1024; // 256 KB
const OVERLAY_NAME = "file-attachment-preview";

let is_initialized = false;

function update_nav_arrows(): void {
    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);
    const show_arrows = attachment_navigator.get_total() > 1;
    $overlay.find(".file-preview-nav-prev").toggleClass("visible", show_arrows);
    $overlay.find(".file-preview-nav-next").toggleClass("visible", show_arrows);
}

function get_extension(filename: string): string {
    const dot_index = filename.lastIndexOf(".");
    if (dot_index === -1) {
        return "";
    }
    return filename.slice(dot_index + 1).toLowerCase();
}

function get_extra_extensions(): Set<string> {
    const raw = user_settings.file_preview_extensions;
    if (!raw) {
        return new Set();
    }
    return new Set(raw.split(",").map((ext) => ext.trim().toLowerCase()).filter(Boolean));
}

export function should_preview(url: string): boolean {
    const raw = user_settings.file_preview_extensions;
    // "none" disables all previews
    if (raw === "none") {
        return false;
    }
    const filename = decodeURIComponent(url.slice(url.lastIndexOf("/") + 1));
    const ext = get_extension(filename);
    if (!ext) {
        return false;
    }
    return BUILT_IN_PREVIEW_EXTENSIONS.has(ext) || get_extra_extensions().has(ext);
}

function get_download_url(url: string): string {
    try {
        const parsed = new URL(url, window.location.href);
        if (
            parsed.origin === window.location.origin &&
            parsed.pathname.startsWith("/user_uploads/")
        ) {
            parsed.pathname =
                "/user_uploads/download/" +
                parsed.pathname.slice("/user_uploads/".length);
            return parsed.href;
        }
    } catch {
        // Fall through to return original URL
    }
    return url;
}

function show_loading(): void {
    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);
    $overlay.find(".file-preview-loading").addClass("show");
    $overlay.find(".file-preview-rendered").removeClass("show");
    $overlay.find(".file-preview-error").removeClass("show");
}

function show_rendered(html: string, is_markdown: boolean): void {
    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);
    const $rendered = $overlay.find(".file-preview-rendered");
    $rendered.html(html);
    $rendered.toggleClass("rendered-markdown", is_markdown);
    $overlay.find(".file-preview-loading").removeClass("show");
    $rendered.addClass("show");
    $overlay.find(".file-preview-error").removeClass("show");
}

function show_error(message: string): void {
    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);
    $overlay.find(".file-preview-loading").removeClass("show");
    $overlay.find(".file-preview-rendered").removeClass("show");
    const $error = $overlay.find(".file-preview-error");
    $error.find(".file-preview-error-message").text(message);
    $error.addClass("show");
}

function escape_html(text: string): string {
    const div = document.createElement("div");
    div.append(document.createTextNode(text));
    return div.innerHTML;
}

function parse_csv(text: string): string[][] {
    const rows: string[][] = [];
    let current_row: string[] = [];
    let current_field = "";
    let in_quotes = false;

    for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (in_quotes) {
            if (ch === '"') {
                if (i + 1 < text.length && text[i + 1] === '"') {
                    current_field += '"';
                    i++;
                } else {
                    in_quotes = false;
                }
            } else {
                current_field += ch;
            }
        } else if (ch === '"') {
            in_quotes = true;
        } else if (ch === ",") {
            current_row.push(current_field);
            current_field = "";
        } else if (ch === "\n" || ch === "\r") {
            if (ch === "\r" && i + 1 < text.length && text[i + 1] === "\n") {
                i++;
            }
            current_row.push(current_field);
            current_field = "";
            if (current_row.some((f) => f.length > 0)) {
                rows.push(current_row);
            }
            current_row = [];
        } else {
            current_field += ch;
        }
    }
    current_row.push(current_field);
    if (current_row.some((f) => f.length > 0)) {
        rows.push(current_row);
    }
    return rows;
}

function render_csv_table(text: string): string {
    const rows = parse_csv(text);
    if (rows.length === 0) {
        return `<pre><code>${escape_html(text)}</code></pre>`;
    }

    const header = rows[0]!;
    const body_rows = rows.slice(1);

    let html = '<div class="file-preview-csv-wrapper"><table class="file-preview-csv-table"><thead><tr>';
    for (const cell of header) {
        html += `<th>${escape_html(cell)}</th>`;
    }
    html += "</tr></thead><tbody>";
    for (const row of body_rows) {
        html += "<tr>";
        for (let i = 0; i < header.length; i++) {
            html += `<td>${escape_html(row[i] ?? "")}</td>`;
        }
        html += "</tr>";
    }
    html += "</tbody></table></div>";
    return html;
}

// PDF state for multi-page navigation — managed by the dynamically
// imported pdf_preview module.  We keep a local reference for the
// click handlers that need synchronous access to the state.
let pdf_preview_mod: typeof import("./pdf_preview.ts") | null = null;

// Lazy-load the PDF preview module (and its pdfjs-dist dependency).
// Isolated into its own module so that pdfjs-dist (ESM-only) doesn't
// prevent the CJS test runner from loading this file.
async function load_pdf_preview(): Promise<typeof import("./pdf_preview.ts")> {
    if (!pdf_preview_mod) {
        pdf_preview_mod = await import("./pdf_preview.ts");
    }
    return pdf_preview_mod;
}

function render_markdown_via_server(text: string): void {
    // Use Zulip's server-side markdown renderer for accurate preview.
    void channel.post({
        url: "/json/messages/render",
        data: {content: text},
        success(response_data) {
            const data = message_render_response_schema.parse(response_data);
            show_rendered(data.rendered, true);
        },
        error() {
            blueslip.warn("Server markdown render failed, using fallback");
            show_rendered(`<pre><code>${escape_html(text)}</code></pre>`, false);
        },
    });
}

function render_content(text: string, ext: string): void {
    if (ext === "md") {
        render_markdown_via_server(text);
        return;
    }

    if (ext === "csv") {
        show_rendered(render_csv_table(text), false);
        return;
    }

    // Try syntax highlighting for known source code extensions
    const language = EXT_TO_HLJS_LANGUAGE[ext];
    if (language) {
        const highlighted = hljs.highlight(text, {language});
        show_rendered(
            `<pre><code class="hljs language-${language}">${highlighted.value}</code></pre>`,
            false,
        );
        return;
    }

    // For unknown extensions, show as plain text only if in the
    // allowed set (built-in or user-configured extras). Otherwise
    // the file should not have reached here — show a download prompt.
    show_rendered(`<pre><code>${escape_html(text)}</code></pre>`, false);
}

export async function open_preview(url: string, filename: string): Promise<void> {
    if (overlays.any_active()) {
        overlays.close_active();
    }

    const download_url = get_download_url(url);
    const ext = get_extension(filename);

    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);
    $overlay.find(".file-preview-filename").text(filename);
    $overlay.find(".file-preview-download").attr("href", download_url);
    $overlay.find(".file-preview-error-download").attr("href", download_url);

    overlays.open_overlay({
        name: OVERLAY_NAME,
        $overlay,
        on_close() {
            $overlay.find(".file-preview-rendered").empty().removeClass("show rendered-markdown");
            $overlay.find(".file-preview-loading").removeClass("show");
            $overlay.find(".file-preview-error").removeClass("show");
            pdf_preview_mod?.clear_pdf_state();
        },
    });

    // Set up attachment navigation
    attachment_navigator.start_navigation(url);
    update_nav_arrows();

    show_loading();

    // PDF files rendered via pdf.js (secure canvas rendering, no iframe)
    if (ext === "pdf") {
        const pdf_mod = await load_pdf_preview();
        await pdf_mod.show_pdf(url, $overlay, show_error);
        return;
    }

    try {
        const response = await fetch(url);

        if (!response.ok) {
            show_error(
                $t(
                    {defaultMessage: "Could not load file (HTTP {status})"},
                    {status: response.status},
                ),
            );
            return;
        }

        const content_length = response.headers.get("Content-Length");
        if (content_length && Number.parseInt(content_length, 10) > MAX_PREVIEW_SIZE) {
            show_error($t({defaultMessage: "File is too large to preview (max 256 KB)."}));
            return;
        }

        const buffer = await response.arrayBuffer();

        if (buffer.byteLength > MAX_PREVIEW_SIZE) {
            show_error($t({defaultMessage: "File is too large to preview (max 256 KB)."}));
            return;
        }

        let text: string;
        try {
            const decoder = new TextDecoder("utf-8", {fatal: true});
            text = decoder.decode(buffer);
        } catch {
            show_error(
                $t({
                    defaultMessage:
                        "This file appears to contain binary content and cannot be previewed.",
                }),
            );
            return;
        }

        render_content(text, ext);
    } catch (error) {
        blueslip.warn("Error loading text attachment preview", {error});
        show_error($t({defaultMessage: "An error occurred while loading the preview."}));
    }
}

// Open the overlay for a file type that cannot be previewed.
// Shows only the filename and download button, with navigation arrows.
export function open_download_only(url: string, filename: string): void {
    if (overlays.any_active()) {
        overlays.close_active();
    }

    const download_url = get_download_url(url);

    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);
    $overlay.find(".file-preview-filename").text(filename);
    $overlay.find(".file-preview-download").attr("href", download_url);
    $overlay.find(".file-preview-error-download").attr("href", download_url);

    overlays.open_overlay({
        name: OVERLAY_NAME,
        $overlay,
        on_close() {
            $overlay.find(".file-preview-rendered").empty().removeClass("show rendered-markdown");
            $overlay.find(".file-preview-loading").removeClass("show");
            $overlay.find(".file-preview-error").removeClass("show");
            pdf_preview_mod?.clear_pdf_state();
        },
    });

    attachment_navigator.start_navigation(url);
    update_nav_arrows();

    show_error(
        $t({defaultMessage: "No preview available for this file type. Use the Download button to save it."}),
    );
}

export function initialize(): void {
    if (is_initialized) {
        return;
    }
    is_initialized = true;

    const rendered = render_file_attachment_preview();
    $("body").append($(rendered));

    const $overlay = $(`#${CSS.escape(OVERLAY_NAME)}-overlay`);

    $overlay.on("click", ".file-preview-close", (e) => {
        e.preventDefault();
        e.stopPropagation();
        overlays.close_overlay(OVERLAY_NAME);
    });

    $overlay.on("click", ".file-preview-download", function () {
        this.blur();
    });

    $overlay.on("click", ".file-preview-error-download", function () {
        this.blur();
    });

    // PDF page navigation handlers
    $overlay.on("click", ".file-preview-pdf-prev", (e) => {
        e.preventDefault();
        const state = pdf_preview_mod?.get_pdf_state();
        if (state && state.current_page > 1) {
            void pdf_preview_mod!.render_pdf_page(state.current_page - 1, $overlay, show_error);
        }
    });

    $overlay.on("click", ".file-preview-pdf-next", (e) => {
        e.preventDefault();
        const state = pdf_preview_mod?.get_pdf_state();
        if (state && state.current_page < state.total_pages) {
            void pdf_preview_mod!.render_pdf_page(state.current_page + 1, $overlay, show_error);
        }
    });

    // Attachment navigation handlers
    $overlay.on("click", ".file-preview-nav-prev", (e) => {
        e.preventDefault();
        e.stopPropagation();
        attachment_navigator.prev();
    });

    $overlay.on("click", ".file-preview-nav-next", (e) => {
        e.preventDefault();
        e.stopPropagation();
        attachment_navigator.next();
    });
}

// Export for use by hotkey.ts
export function prev(): void {
    attachment_navigator.prev();
}

export function next(): void {
    attachment_navigator.next();
}
