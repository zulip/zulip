require "shellwords"

Puppet::Functions.create_function(:zulipconf_nagios_hosts) do
  def zulipconf_nagios_hosts
    section = "nagios"
    prefix = "hosts_"
    zulip_conf_path = Facter.value("zulip_conf_path")
    keys = `/usr/bin/crudini --get -- #{[zulip_conf_path, section].shelljoin} 2>&1`; result = $?.success?
    if result
      filtered_keys = keys.lines.map { |l| l.strip }.select { |l| l.start_with?(prefix) }
      all_values = []
      filtered_keys.each do |key|
        values = `/usr/bin/crudini --get -- #{[zulip_conf_path, section, key].shelljoin} 2>&1`; result = $?.success?
        if result
          all_values += values.strip.split(/,\s*/)
        end
      end
      return all_values
    else
      return []
    end
  end
end
