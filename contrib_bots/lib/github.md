# Zulip Github API
## Introduction
The github.api script is designed to allow bot developers to interface with any part of the github api
It should make it simple and easy for you to implement github into your bot.
## Getting Started
1. Make a .github folder in your home directory, and make a github.conf file in it
2. Make a Github personal access token, with access to the features you need [here](https://github.com/settings/tokens)
3. Fill in the properties of the github.conf file using this example:
```
[github]
github_repo=REPO
github_repo_owner=REPO_OWNER
github_username=USERNAME
github_token=TOKEN
```
4. Add `from . import github` to the top of your script (as long as the script is in the contrib_bots/lib directory)
5. Initialise the class by adding `gh = github()`
6. Authenticate the session with `gh.auth()`
7. Use any features you want to use. Visit [The developer Website](https://developer.github.com/v3)
## Making a POST request
See [The developer Website](https://developer.github.com/v3) for reference.
To make a POST request, use `gh.post(url, params)`

`url` is the **FULL** url to post to.

`params` is the JSON code that will be sent to the URL

Simply set the URL to `gh.base_url`, and make some JSON code that corresponds to the code on the [The developer Website](https://developer.github.com/v3)

**WARNING** `gh.base_url` is the **base** url for the repo, **NOT** the final URL. See [The developer Website](https://developer.github.com/v3) for which URL to use. `base_url` would be https://api.github.com/repos/github_repo_owner/github_repo

For example, this code will send an issue to the configured repo with the Title `title` and the Content `content`
```python
from . import github

gh = github.github()
gh.auth()
params = {
    'title' : title,
    'body' : body,
    'assignee' : '',
    'labels' : ['']
}
gh.post(gh.base_url + '/issues', params)
```
The `gh.post` function will automatically post any error messages to the console, however, if you would like to handle this youself, you can use:
```python
r = gh.post(gh.base_url + '/issues', params, True)
if r.ok:
    print('success!')
```
**PLEASE NOTE** You will need to use `import requests` to use this functionality
**I would strongly advise comparing this code to [the Github API](https://developer.github.com/v3/issues/#create-an-issue) in order to understand how the API works.**

## Making a GET request
Making a GET request is almost identical to making a POST request, apart from you use the `github.get()` function.
In this example, we will get one issue.
```python
from . import github
import requests
import json

gh = github.github()
gh.auth()

r = gh.post(gh.base_url + '/issues/10')
content = json.loads(gh.content)
print(content)
```
**I would strongly advise comparing this code to [the Github API](https://developer.github.com/v3/issues/#get-a-single-issue) in order to understand how the API works.**

