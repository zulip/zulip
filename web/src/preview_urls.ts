import $ from "jquery";
import * as z from "zod/mini";

import render_previewable_url_tooltip from "../templates/previewable_url_tooltip.hbs";

import {$t} from "./i18n.ts";
import type {PreviewInstance} from "./tippyjs";
import * as ui_util from "./ui_util.ts";

const github_issue_schema = z.object({
    platform: z.literal("github"),
    type: z.literal("issue"),
    title: z.string(),
    owner: z.string(),
    repo: z.string(),
    issue_number: z.string(),
    author: z.string(),
    state: z.enum(["open", "closed", "merged"]),
    state_reason: z.nullable(z.string()),
});

const github_pull_request_schema = z.object({
    platform: z.literal("github"),
    type: z.literal("pull_request"),
    draft: z.boolean(),
    merged_at: z.nullable(z.string()),
    title: z.string(),
    owner: z.string(),
    repo: z.string(),
    issue_number: z.string(),
    author: z.string(),
    state: z.enum(["open", "closed", "merged"]),
});

const github_preview_response_schema = z.discriminatedUnion("type", [
    github_issue_schema,
    github_pull_request_schema,
]);

export const preview_response_schema = z.discriminatedUnion("platform", [
    github_preview_response_schema,
]);

export type URLPreviewData = z.infer<typeof preview_response_schema>;

function set_tooltip_content_for_github_preview(
    preview_data: URLPreviewData,
    instance: PreviewInstance,
): void {
    let icon;
    if (preview_data.type === "pull_request") {
        icon = preview_data.state;
        const merged = preview_data.merged_at !== null;
        if (preview_data.draft) {
            icon += "-draft";
        } else if (merged) {
            icon += "-merged";
        }
    } else {
        icon = [preview_data.state, preview_data.state_reason].filter(Boolean).join("-");
    }
    const issue = `${preview_data.owner}/${preview_data.repo}#${preview_data.issue_number}`;
    instance.setContent(
        ui_util.parse_html(
            render_previewable_url_tooltip({
                hover_preview_title: preview_data.title,
                hover_preview_details: $t(
                    {
                        defaultMessage: "{issue} opened by { author }",
                    },
                    {
                        author: preview_data.author,
                        issue,
                    },
                ),
                hover_preview_icon_path: `/static/images/github/${preview_data.type}/${icon}.svg`,
            }),
        ),
    );
}

export function set_url_preview_tooltip_content(
    preview_data: URLPreviewData,
    instance: PreviewInstance,
): void {
    switch (preview_data.platform) {
        case "github":
            set_tooltip_content_for_github_preview(preview_data, instance);
    }
}

export function is_url_previewable(href: string): boolean {
    try {
        const url = new URL(href);
        if (
            ["https:", "http:"].includes(url.protocol) &&
            ["github.com", "www.github.com"].includes(url.hostname) &&
            url.port === ""
        ) {
            const work_item = url.pathname.split("/")[3];
            return work_item !== undefined && ["issues", "pull"].includes(work_item);
        }
        return false;
    } catch {
        return false;
    }
}

export function initialize(): void {
    $("#main_div").on(
        "mouseenter",
        ".rendered_markdown a",
        (e: JQuery.TriggeredEvent<HTMLElement, undefined, HTMLElement, HTMLElement>) => {
            const elt: HTMLElement = e.target;
            const href = elt.getAttribute("href");
            if (!href || elt.classList.contains("previewable")) {
                return;
            }
            if (is_url_previewable(href)) {
                // We want to avoid showing browser tooltips for previewable
                // links.
                elt.removeAttribute("title");
                elt.classList.add("previewable");
            }
        },
    );
}
