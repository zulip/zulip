import type {Instance as TippyInstance} from "tippy.js";
import * as z from "zod/mini";

import render_url_preview_tooltip from "../templates/url_preview_tooltip.hbs";

import {$t} from "./i18n.ts";
import * as ui_util from "./ui_util.ts";

const github_issue_schema = z.object({
    platform: z.literal("github"),
    type: z.literal("issue"),
    title: z.string(),
    owner: z.string(),
    repo: z.string(),
    number: z.string(),
    author: z.string(),
    state: z.enum(["open", "closed"]),
    state_reason: z.nullable(z.string()),
});
type GithubIssueData = z.infer<typeof github_issue_schema>;

const github_pull_request_schema = z.object({
    platform: z.literal("github"),
    type: z.literal("pull_request"),
    title: z.string(),
    owner: z.string(),
    repo: z.string(),
    number: z.string(),
    author: z.string(),
    state: z.enum(["open", "closed"]),
    draft: z.boolean(),
    merged_at: z.nullable(z.string()),
});
type GithubPullRequestData = z.infer<typeof github_pull_request_schema>;

const github_preview_response_schema = z.discriminatedUnion("type", [
    github_issue_schema,
    github_pull_request_schema,
]);

export const preview_response_schema = z.discriminatedUnion("platform", [
    github_preview_response_schema,
]);

export type URLPreviewData = z.infer<typeof preview_response_schema>;

// State icons live at static/images/github/{issue,pull_request}/{name}.svg.
// These helpers map an issue or pull request's state to the icon file name.
export function github_issue_icon_name(data: GithubIssueData): string {
    if (data.state === "closed") {
        if (data.state_reason === "completed" || data.state_reason === "not_planned") {
            return `closed-${data.state_reason}`;
        }
        return "closed";
    }
    return "open";
}

export function github_pull_request_icon_name(data: GithubPullRequestData): string {
    if (data.merged_at !== null) {
        return "closed-merged";
    }
    if (data.draft) {
        return "open-draft";
    }
    return data.state;
}

function set_tooltip_content_for_github_preview(
    data: GithubIssueData | GithubPullRequestData,
    instance: TippyInstance,
): void {
    const icon_name =
        data.type === "pull_request"
            ? github_pull_request_icon_name(data)
            : github_issue_icon_name(data);
    const issue = `${data.owner}/${data.repo}#${data.number}`;
    instance.setContent(
        ui_util.parse_html(
            render_url_preview_tooltip({
                title: data.title,
                details: $t(
                    {defaultMessage: "{issue} opened by {author}"},
                    {author: data.author, issue},
                ),
                icon_path: `/static/images/github/${data.type}/${icon_name}.svg`,
            }),
        ),
    );
}

export function set_url_preview_tooltip_content(
    preview_data: URLPreviewData,
    instance: TippyInstance,
): void {
    switch (preview_data.platform) {
        case "github":
            set_tooltip_content_for_github_preview(preview_data, instance);
            return;
        default:
            // Exhaustiveness: adding another platform without a case above is
            // a compile error here.
            preview_data.platform satisfies never;
    }
}
