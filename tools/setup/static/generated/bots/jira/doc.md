# Jira Bot

## Setup

To use Jira Bot, first set up `jira.conf`. `jira.conf` takes 3 options:

 - username (an email or username that can access your Jira),
 - password (the password for that username), and
 - domain (a domain like `example.atlassian.net`)

## Usage

### get

`get` takes in an issue key and sends back information about that issue. For example,

you:

 > @**Jira Bot** get "BOTS-13"

Jira Bot:

 > **Issue *BOTS-13*: Create Jira Bot**
 >
 > - Type: *Task*
 > - Description:
 > > Jira Bot would connect to Jira.
 > - Creator: *admin*
 > - Project: *Bots*
 > - Priority: *Medium*
 > - Status: *To Do*

### create

`create` creates an issue using its

 - summary,
 - project,
 - type,
 - description *(optional)*,
 - assignee *(optional)*,
 - priority *(optional)*,
 - labels *(optional)*, and
 - due date *(optional)*

For example, to create an issue with every option,

you:

 > @**Jira Bot** create issue "Make an issue" in project "BOTS"' with type "Task" with description
 > "This is a description" assigned to "skunkmb" with priority "Medium" labeled "issues, testing"
 > due "2017-01-23"

Jira Bot:

 > Issue *BOTS-16* is up! https://example.atlassian.net/browse/BOTS-16

### edit

`edit` is like create, but changes an existing issue using its

 - summary,
 - project *(optional)*,
 - type *(optional)*,
 - description *(optional)*,
 - assignee *(optional)*,
 - priority *(optional)*,
 - labels *(optional)*, and
 - due date *(optional)*.

For example, to change every part of an issue,

you:

 > @**Jira Bot** edit issue "BOTS-16" to use summary "Change the summary" to use project
 > "NEWBOTS" to use type "Bug" to use description "This is a new description" by assigning
 > to "admin" to use priority "Low" by labeling "new, labels" by making due "2018-12-5"

Jira Bot:

 > Issue *BOTS-16* was edited! https://example.atlassian.net/browse/BOTS-16
