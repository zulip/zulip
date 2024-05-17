require "shellwords"

Puppet::Functions.create_function(:zulipconf) do
  def zulipconf(section, key, default)
    zulip_conf_path = Facter.value("zulip_conf_path")
    output = `/usr/bin/crudini --get -- #{[zulip_conf_path, section, key].shelljoin} 2>&1`; result = $?.success?
    if result
      if [true, false].include? default
        # If the default is a bool, coerce into a bool.  This list is also
        # maintained in scripts/lib/zulip_tools.py
        ["1", "y", "t", "true", "yes", "enable", "enabled"].include? output.strip.downcase
      else
        output.strip
      end
    else
      default
    end
  end
end
