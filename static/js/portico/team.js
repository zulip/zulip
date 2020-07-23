const contributors_list = page_params.contrib;

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

function contrib_total_commits(contributor) {
    let commits = 0;
    Object.keys(repo_name_to_tab_name).forEach((repo_name) => {
        commits += contributor[repo_name] || 0;
    });
    return commits;
}

// TODO (for v2 of /team contributors):
//   - Make tab header responsive.
//   - Display full name instead of github username.
export default function render_tabs() {
    const template = _.template($("#contributors-template").html());
    // The GitHub API limits the number of contributors per repo to somwhere in the 300s.
    // Since zulip/zulip repo has the highest number of contributors by far, we only show
    // contributors who have atleast the same number of contributions than the last contributor
    // returned by the API for zulip/zulip repo.
    const least_server_commits = _.chain(contributors_list)
        .filter("zulip")
        .sortBy("zulip")
        .value()[0].zulip;

    const total_tab_html = _.chain(contributors_list)
        .map((c) => ({
            name: c.name,
            avatar: c.avatar,
            commits: contrib_total_commits(c),
        }))
        .sortBy("commits")
        .reverse()
        .filter((c) => c.commits >= least_server_commits)
        .map((c) => template(c))
        .value()
        .join("");

    $("#tab-total").html(total_tab_html);

    for (const repo_name of Object.keys(repo_name_to_tab_name)) {
        const tab_name = repo_name_to_tab_name[repo_name];
        if (!tab_name) {
            continue;
        }
        // Set as the loading template for now, and load when clicked.
        $("#tab-" + tab_name).html($("#loading-template").html());

        $("#" + tab_name).on("click", () => {
            if (!loaded_repos.includes(repo_name)) {
                const html = _.chain(contributors_list)
                    .filter(repo_name)
                    .sortBy(repo_name)
                    .reverse()
                    .map((c) =>
                        template({
                            name: c.name,
                            avatar: c.avatar,
                            commits: c[repo_name],
                        }),
                    )
                    .value()
                    .join("");

                $("#tab-" + tab_name).html(html);

                loaded_repos.push(repo_name);
            }
        });
    }
}
