import _ from "lodash";

const contributors_list = page_params.contributors;

const repo_name_to_tab_name = {
    zulip: "server",
    "zulip-desktop": "desktop",
    "zulip-mobile": "mobile",
    "python-zulip-api": "python-zulip-api",
    "zulip-js": "zulip-js",
    zulipbot: "zulipbot",
    "zulip-terminal": "terminal",
    "zulip-ios-legacy": "",
    "zulip-android": "",
};

// Remember the loaded repositories so that HTML is not redundantly edited
// if a user leaves and then revisits the same tab.
const loaded_repos = [];

function calculate_total_commits(contributor) {
    let commits = 0;
    for (const repo_name of Object.keys(repo_name_to_tab_name)) {
        commits += contributor[repo_name] || 0;
    }
    return commits;
}

function get_profile_url(contributor, tab_name) {
    const commit_email_linked_to_github = "github_username" in contributor;

    if (commit_email_linked_to_github) {
        return "https://github.com/" + contributor.github_username;
    }

    const email = contributor.email;

    if (tab_name) {
        return `https://github.com/zulip/${tab_name}/commits?author=${email}`;
    }

    for (const repo_name in repo_name_to_tab_name) {
        if (repo_name in contributor) {
            return `https://github.com/zulip/${repo_name}/commits?author=${email}`;
        }
    }

    return undefined;
}

function get_display_name(contributor) {
    if (contributor.github_username) {
        return "@" + contributor.github_username;
    }
    return contributor.name;
}

// TODO (for v2 of /team contributors):
//   - Make tab header responsive.
//   - Display full name instead of GitHub username.
export default function render_tabs() {
    const template = _.template($("#contributors-template").html());
    const total_tab_html = contributors_list
        .map((c) => ({
            name: get_display_name(c),
            github_username: c.github_username,
            avatar: c.avatar,
            profile_url: get_profile_url(c),
            commits: calculate_total_commits(c),
        }))
        .sort((a, b) => (a.commits < b.commits ? 1 : a.commits > b.commits ? -1 : 0))
        .map((c) => template(c))
        .join("");

    $("#tab-total").html(total_tab_html);

    for (const repo_name of Object.keys(repo_name_to_tab_name)) {
        const tab_name = repo_name_to_tab_name[repo_name];
        if (!tab_name) {
            continue;
        }
        // Set as the loading template for now, and load when clicked.
        $(`#tab-${CSS.escape(tab_name)}`).html($("#loading-template").html());

        $(`#${CSS.escape(tab_name)}`).on("click", () => {
            if (!loaded_repos.includes(repo_name)) {
                const html = contributors_list
                    .filter((c) => c[repo_name])
                    .sort((a, b) =>
                        a[repo_name] < b[repo_name] ? 1 : a[repo_name] > b[repo_name] ? -1 : 0,
                    )
                    .map((c) =>
                        template({
                            name: get_display_name(c),
                            github_username: c.github_username,
                            avatar: c.avatar,
                            profile_url: get_profile_url(c),
                            commits: c[repo_name],
                        }),
                    )
                    .join("");

                $(`#tab-${CSS.escape(tab_name)}`).html(html);

                loaded_repos.push(repo_name);
            }
        });
    }
}
