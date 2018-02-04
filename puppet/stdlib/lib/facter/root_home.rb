# A facter fact to determine the root home directory.
# This varies on PE supported platforms and may be
# reconfigured by the end user.

module Facter::Util::RootHome
  class << self
  def get_root_home
    root_ent = Facter::Util::Resolution.exec("getent passwd root")
    # The home directory is the sixth element in the passwd entry
    # If the platform doesn't have getent, root_ent will be nil and we should
    # return it straight away.
    root_ent && root_ent.split(":")[5]
  end
  end
end

Facter.add(:root_home) do
  setcode { Facter::Util::RootHome.get_root_home }
end
