# @summary Push the merge_base to a git repo after deploy
#
class zulip::hooks::push_git_ref {
  include zulip::hooks::base

  zulip::hooks::file { [
    'post-deploy.d/push_git_ref.hook',
  ]: }
}
