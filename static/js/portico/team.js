// Contributor list is baked into the /team's page template, so we can silent
// eslint's error.
/* global contributors_list */

var repos = ['server', 'desktop', 'mobile', 'python-zulip-api', 'zulipbot'];

function contrib_total_commits(contrib) {
    var commits = 0;
    repos.forEach(function (repo) {
        commits += contrib[repo] || 0;
    });
    return commits;
}

// TODO (for v2 of /team contributors):
//   - Freeze contributions data for legacy repo (ios, android) and include them
//     in totals tab.
//   - Lazy-render all but the total tab.
//   - Make tab header responsive.
//   - Display full name instead of github username.
export default function render_tabs() {
    var template = _.template($('#contributors-template').html());

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
        .map(function (c) { return template(c); })
        .value()
        .join('');

    $('#tab-total').html(total_tab_html);

    _.each(repos, function (repo) {
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
    });
}
