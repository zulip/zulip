# @summary Temporary shim for base profile.
#
# Any explicit PUPPET_CLASSES of this file can be removed.
class zulip::base {
  include zulip::profile::base
}
