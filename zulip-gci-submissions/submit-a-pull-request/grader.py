import sys
import argparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument('pr_number')
parser.add_argument('username')
args = parser.parse_args()

url = 'https://api.github.com/repos/zulip/zulip-gci-submissions/pulls/{}'.format(args.pr_number)
response = requests.get(url)
data = response.json()

lgtm = True

def fail(failure):
	print(failure)
	global lgtm
	lgtm = False

def report_and_exit():
	if lgtm:
		print("LGTM.")
	else:
		print("That doesn't LGTM.")
	sys.exit()

# Check that the PR exists.
if response.status_code == 404:
	fail("PR {} does not exist.".format(url))
	report_and_exit()

# Check that the PR is not closed.
if data['state'] == "closed":
	fail("PR {} is closed.".format(url))
	report_and_exit()

# Check that the PR has no merge conflicts.
if data['rebaseable'] == False:
	fail("PR {} has merge conflicts.".format())

# Check that the PR has the right title.
title = data['title']
expected_titles = ["Submit a Pull Request", "Submit a pull request"]
if not (title in expected_titles):
	fail("PR has a wrong title. Submitted: '{}'. Expected: '{}'.".format(title, expected_titles[0]))

# Check that the PR has the right branch name.
branch = data['head']['ref']
expected_branch = "submit-a-pull-request"
if branch != expected_branch:
	fail("PR has a wrong branch name. Submitted: '{}'. Expected: '{}'.".format(branch, expected_branch))

# Check that the PR is against zulip:master.
merge_into_branch = data['base']['label']
expected_merge_into_branch = 'zulip:master'
if merge_into_branch != expected_merge_into_branch:
	fail("PR is against the wrong branch. Submitted: ''. Expected: '{}'.".format(merge_into_branch, expected_merge_into_branch))

# Check that the PR has the right number of commits.
commits = data['commits']
expected_commits = 2
if commits != expected_commits:
	fail("PR has the wrong number of commits. Submitted: ''. Expected: '{}'.".format(commits, expected_commits))

# Check the PR content.
patch_response = requests.get(data['patch_url'])
patch_lines = patch_response.content.decode().split('\n')
expected_lines = [
	'*',
	'*',
	'*',
	'Subject: [PATCH 1/2] Add hello-world.md.',
	'',
	'---',
	' submit-a-pull-request/{}/hello-world.md | 2 ++',
	' 1 file changed, 2 insertions(+)',
	' create mode 100644 submit-a-pull-request/{}/hello-world.md',
	'',
	'diff --git a/submit-a-pull-request/{0}/hello-world.md b/submit-a-pull-request/{0}/hello-world.md',
	'new file mode 100644',
	'*',
	'--- /dev/null',
	'+++ b/submit-a-pull-request/{}/hello-world.md',
	'@@ -0,0 +1,2 @@',
	'+Hello world',
	'+I am username. :tada:',
	'',
	'*',
	'*',
	'*',
	'Subject: [PATCH 2/2] hello-world.md: Change username to GitHub handle.',
	'',
	'---',
	' submit-a-pull-request/{}/hello-world.md | 2 +-',
	' 1 file changed, 1 insertion(+), 1 deletion(-)',
	'',
	'diff --git a/submit-a-pull-request/{0}/hello-world.md b/submit-a-pull-request/{0}/hello-world.md',
	'*',
	'--- a/submit-a-pull-request/{}/hello-world.md',
	'+++ b/submit-a-pull-request/{}/hello-world.md',
	'@@ -1,2 +1,2 @@',
	' Hello world',
	'-I am username. :tada:',
	'+I am {}. :tada:',
	'',
]
for patch, expected in zip(patch_lines, expected_lines):
	if expected == '*':
		continue
	expected_line = expected.format(args.username)
	patch_line = patch
	if expected_line != patch_line:
		fail("Invalid PR content. Submitted: '{}'. Expected: '{}'.".format(patch_line, expected_line))

report_and_exit()
