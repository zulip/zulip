import $ from "jquery";
import _ from "lodash";

// The list of repository names is duplicated here in order to provide
// a clear type for Contributor objects.
//
// TODO: We can avoid this if we introduce a `contributions` object
// referenced from Contributor, rather than having repository names be
// direct keys in the namespace that also has `email`.
const all_repository_names = [
    "docker-zulip",
    "errbot-backend-zulip",
    "github-actions-zulip",
    "hubot-zulip",
    "puppet-zulip",
    "python-zulip-api",
    "trello-to-zulip",
    "swift-zulip-api",
    "zulint",
    "zulip",
    "zulip-android-legacy",
    "zulip-architecture",
    "zulip-archive",
    "zulip-csharp",
    "zulip-desktop",
    "zulip-desktop-legacy",
    "zulip-flutter",
    "zulip-ios-legacy",
    "zulip-js",
    "zulip-mobile",
    "zulip-redmine-plugin",
    "zulip-terminal",
    "zulip-zapier",
    "zulipbot",
] as const;

const all_tab_names = [
    "server",
    "desktop",
    "mobile",
    "terminal",
    "api-clients",
    "devtools",
] as const;

type RepositoryName = (typeof all_repository_names)[number];
type TabName = (typeof all_tab_names)[number];

const tab_name_to_repo_list: Record<TabName, RepositoryName[]> = {
    server: ["zulip", "docker-zulip"],
    desktop: ["zulip-desktop", "zulip-desktop-legacy"],
    mobile: ["zulip-mobile", "zulip-flutter", "zulip-ios-legacy", "zulip-android-legacy"],
    terminal: ["zulip-terminal"],
    "api-clients": [
        "python-zulip-api",
        "zulip-js",
        "zulip-archive",
        "errbot-backend-zulip",
        "github-actions-zulip",
        "hubot-zulip",
        "puppet-zulip",
        "trello-to-zulip",
        "swift-zulip-api",
        "zulip-csharp",
        "zulip-redmine-plugin",
        "zulip-zapier",
    ],
    devtools: ["zulipbot", "zulint", "zulip-architecture"],
};

export type Contributor = {
    avatar: string;
    email?: string;
    github_username?: string;
    name: string;
} & {
    [K in RepositoryName]?: number;
};
type ContributorData = {
    avatar: string;
    email?: string;
    github_username?: string;
    name: string;
    total_commits: number;
};

// Remember the loaded repositories so that HTML is not redundantly edited
// if a user leaves and then revisits the same tab.
const loaded_tabs: string[] = [];

function calculate_total_commits(contributor: Contributor): number {
    let commits = 0;
    for (const repo_name of all_repository_names) {
        commits += contributor[repo_name] ?? 0;
    }
    return commits;
}

function get_profile_url(contributor: Contributor, tab_name?: string): string | undefined {
    if (contributor.github_username) {
        return `https://github.com/${contributor.github_username}`;
    }

    const email = contributor.email;
    if (!email) {
        return undefined;
    }

    if (tab_name) {
        return `https://github.com/zulip/${tab_name}/commits?author=${email}`;
    }

    for (const repo_name of all_repository_names) {
        if (repo_name in contributor) {
            return `https://github.com/zulip/${repo_name}/commits?author=${email}`;
        }
    }

    return undefined;
}

function get_display_name(contributor: Contributor): string {
    if (contributor.github_username) {
        return "@" + contributor.github_username;
    }
    return contributor.name;
}

function exclude_bot_contributors(contributor: Contributor): boolean {
    return contributor.github_username !== "dependabot[bot]";
}

// TODO (for v2 of /team/ contributors):
//   - Make tab header responsive.
//   - Display full name instead of GitHub username.
export default function render_tabs(contributors: Contributor[]): void {
    const template = _.template($("#contributors-template").html());
    const count_template = _.template($("#count-template").html());
    const total_count_template = _.template($("#total-count-template").html());
    const contributors_list = contributors
        ? contributors.filter((c) => exclude_bot_contributors(c))
        : [];
    const mapped_contributors_list = contributors_list.map((c) => ({
        name: get_display_name(c),
        github_username: c.github_username,
        avatar: c.avatar,
        profile_url: get_profile_url(c),
        commits: calculate_total_commits(c),
    }));
    const total_tab_html = mapped_contributors_list
        .sort((a, b) => (a.commits < b.commits ? 1 : a.commits > b.commits ? -1 : 0))
        .map((c) => template(c))
        .join("");

    const hundred_plus_total_contributors = mapped_contributors_list.filter(
        (c) => c.commits >= 100,
    );

    $("#tab-total .contributors-grid").html(total_tab_html);
    $("#tab-total").prepend(
        $(
            total_count_template({
                contributor_count: contributors_list.length,
                tab_name: "total",
                hundred_plus_contributor_count: hundred_plus_total_contributors.length,
            }),
        ),
    );

    for (const tab_name of all_tab_names) {
        const repo_list = tab_name_to_repo_list[tab_name];
        if (!repo_list) {
            continue;
        }
        // Set as the loading template for now, and load when clicked.
        $(`#tab-${CSS.escape(tab_name)} .contributors-grid`).html($("#loading-template").html());

        $(`#${CSS.escape(tab_name)}`).on("click", () => {
            if (!loaded_tabs.includes(tab_name)) {
                const filtered_by_tab: ContributorData[] = contributors_list
                    .filter((c: Contributor) =>
                        repo_list.some((repo_name: RepositoryName) => c[repo_name] !== undefined),
                    )
                    .map((c: Contributor) => ({
                        ..._.pick(c, "avatar", "email", "name", "github_username"),
                        total_commits: repo_list.reduce(
                            (commits: number, repo_name: RepositoryName) =>
                                commits + (c[repo_name] ?? 0),
                            0,
                        ),
                    }));

                const html = filtered_by_tab
                    .sort((a, b) => {
                        const a_commits = a.total_commits;
                        const b_commits = b.total_commits;
                        return a_commits < b_commits ? 1 : a_commits > b_commits ? -1 : 0;
                    })
                    .map((c) =>
                        template({
                            name: get_display_name(c),
                            github_username: c.github_username,
                            avatar: c.avatar,
                            profile_url: get_profile_url(c, tab_name),
                            commits: c.total_commits,
                        }),
                    )
                    .join("");

                $(`#tab-${CSS.escape(tab_name)} .contributors-grid`).html(html);
                const contributor_count = filtered_by_tab.length;
                const hundred_plus_contributor_count = filtered_by_tab.filter((c) => {
                    const commits = c.total_commits;
                    return commits >= 100;
                }).length;
                const repo_url_list = repo_list.map(
                    (repo_name) => `https://github.com/zulip/${repo_name}`,
                );
                $(`#tab-${CSS.escape(tab_name)}`).prepend(
                    $(
                        count_template({
                            contributor_count,
                            repo_list,
                            repo_url_list,
                            hundred_plus_contributor_count,
                        }),
                    ),
                );

                loaded_tabs.push(tab_name);
            }
        });
    }
}
