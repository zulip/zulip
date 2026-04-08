// Separate module for PDF rendering via pdf.js.
// Isolated to keep pdfjs-dist (ESM-only) out of the main
// file_attachment_preview module, which must be loadable by
// the CJS test runner.

import {GlobalWorkerOptions, getDocument} from "pdfjs-dist";

import * as blueslip from "./blueslip.ts";
import {$t} from "./i18n.ts";

// Configure pdf.js worker — webpack resolves the URL via import.meta.url
GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
).href;

// PDF state for multi-page navigation
let pdf_state: {
    total_pages: number;
    current_page: number;
    url: string;
    scale: number;
} | null = null;

export function get_pdf_state(): typeof pdf_state {
    return pdf_state;
}

export function clear_pdf_state(): void {
    pdf_state = null;
}

export async function render_pdf_page(
    page_number: number,
    $overlay: JQuery,
    show_error: (msg: string) => void,
): Promise<void> {
    if (!pdf_state) {
        return;
    }
    const $rendered = $overlay.find(".file-preview-rendered");

    try {
        const pdf = await getDocument(pdf_state.url).promise;
        const page = await pdf.getPage(page_number);

        // Calculate scale to fit the container width
        const $container = $rendered.find(".file-preview-pdf-container");
        const container_width = Math.max($container.width() ?? 800, 400);
        const viewport_unscaled = page.getViewport({scale: 1});
        const fit_scale = (container_width - 40) / viewport_unscaled.width;
        // Apply user zoom and device pixel ratio for crisp rendering
        const dpr = window.devicePixelRatio || 1;
        const scale = Math.min(fit_scale, 2.0) * pdf_state.scale * dpr;
        const viewport = page.getViewport({scale});

        const canvas = $rendered.find<HTMLCanvasElement>(".file-preview-pdf-canvas")[0]!;

        // Set canvas pixel dimensions to the scaled viewport
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        // Set CSS dimensions to display at the logical (non-DPR) size
        canvas.style.width = `${Math.floor(viewport.width / dpr)}px`;
        canvas.style.height = `${Math.floor(viewport.height / dpr)}px`;

        await page.render({canvas, viewport}).promise;

        // Update page indicator
        pdf_state.current_page = page_number;
        $rendered
            .find(".file-preview-pdf-page-indicator")
            .text(`${page_number} / ${pdf_state.total_pages}`);

        // Update button states
        $rendered
            .find(".file-preview-pdf-prev")
            .prop("disabled", page_number <= 1);
        $rendered
            .find(".file-preview-pdf-next")
            .prop("disabled", page_number >= pdf_state.total_pages);

        pdf.destroy();
    } catch (error) {
        blueslip.warn("Error rendering PDF page", {error: String(error)});
        show_error($t({defaultMessage: "An error occurred while rendering the PDF."}));
    }
}

export async function show_pdf(
    url: string,
    $overlay: JQuery,
    show_error: (msg: string) => void,
): Promise<void> {
    const $rendered = $overlay.find(".file-preview-rendered");

    try {
        const pdf = await getDocument(url).promise;
        const total_pages = pdf.numPages;

        pdf_state = {
            total_pages,
            current_page: 1,
            url,
            scale: 1.0,
        };

        // Build PDF viewer UI with page navigation
        let controls_html = "";
        if (total_pages > 1) {
            controls_html = `
                <div class="file-preview-pdf-controls">
                    <button class="file-preview-pdf-prev" disabled>&lsaquo;</button>
                    <span class="file-preview-pdf-page-indicator">1 / ${total_pages}</span>
                    <button class="file-preview-pdf-next" ${total_pages <= 1 ? "disabled" : ""}>&rsaquo;</button>
                </div>`;
        }

        $rendered.html(
            `<div class="file-preview-pdf-container">
                ${controls_html}
                <div class="file-preview-pdf-canvas-wrapper">
                    <canvas class="file-preview-pdf-canvas"></canvas>
                </div>
            </div>`,
        );

        $overlay.find(".file-preview-loading").removeClass("show");
        $rendered.addClass("show");
        $overlay.find(".file-preview-error").removeClass("show");

        // Render the first page directly using the already-loaded document
        const page = await pdf.getPage(1);
        const $container = $rendered.find(".file-preview-pdf-container");
        const container_width = Math.max($container.width() ?? 800, 400);
        const viewport_unscaled = page.getViewport({scale: 1});
        const fit_scale = (container_width - 40) / viewport_unscaled.width;
        const dpr = window.devicePixelRatio || 1;
        const scale = Math.min(fit_scale, 2.0) * dpr;
        const viewport = page.getViewport({scale});

        const canvas = $rendered.find<HTMLCanvasElement>(".file-preview-pdf-canvas")[0]!;
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.style.width = `${Math.floor(viewport.width / dpr)}px`;
        canvas.style.height = `${Math.floor(viewport.height / dpr)}px`;

        await page.render({canvas, viewport}).promise;
        pdf.destroy();
    } catch (error) {
        blueslip.warn("Error loading PDF", {error: String(error)});
        show_error($t({defaultMessage: "Could not load PDF. The file may be corrupted."}));
    }
}
