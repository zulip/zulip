// Contributor list is baked into the /team's page template, so we can silent
// eslint's error.
/* global contributors_list */

// `repos` are repositories to be shown as tabs, whereas `hidden_repos` are
// repositories that should count towards the total but not have tabs.
var repos = ['server', 'desktop', 'mobile', 'python-zulip-api', 'zulip-js', 'zulipbot', 'terminal'];
var hidden_repos = ['zulip-android', 'zulip-ios-legacy'];

// Remember the loaded repositories so that HTML is not redundantly edited
// if a user leaves and then revisits the same tab.
var loaded_repos = [];

function contrib_total_commits(contrib) {
    var commits = 0;
    repos.concat(hidden_repos).forEach(function (repo) {
        commits += contrib[repo] || 0;
    });
    return commits;
}

// TODO (for v2 of /team contributors):
//   - Make tab header responsive.
//   - Display full name instead of github username.
export default function render_tabs() {
    var template = _.template($('#contributors-template').html());

    // Since the Github API limits the number of output to 100, we want to
    // remove anyone in the total tab with less commits than the 100th
    // contributor to the server repo. (See #7470)
    var least_server_commits = _.chain(contributors_list)
        .filter('server')
        .sortBy('server')
        .value()[0].server;

    var total_tab_html = _.chain(contributors_list)
        .map(function (c) {
            return {
                name: c.name,
                avatar: c.avatar,
                commits: contrib_total_commits(c),
            };
        })
        .sortBy('commits')
        .reverse()
        .filter(function (c) { return c.commits >= least_server_commits; })
        .map(function (c) { return template(c); })
        .value()
        .join('');

    $('#tab-total').html(total_tab_html);

    _.each(repos, function (repo) {
        // Set as the loading template for now, and load when clicked.
        $('#tab-' + repo).html($('#loading-template').html());

        $('#' + repo).click(function () {
            if (!_.contains(loaded_repos, repo)) {
                var html = _.chain(contributors_list)
                    .filter(repo)
                    .sortBy(repo)
                    .reverse()
                    .map(function (c) {
                        return template({
                            name: c.name,
                            avatar: c.avatar,
                            commits: c[repo],
                        });
                    })
                    .value()
                    .join('');

                $('#tab-' + repo).html(html);

                loaded_repos.push(repo);
            }
        });
    });
}
