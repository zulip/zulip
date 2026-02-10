require "open3"

Puppet::Functions.create_function(:zulipconf_nagios_hosts) do
  def zulipconf_nagios_hosts
    section = "nagios"
    prefix = "hosts_"
    zulip_conf_path = Facter.value("zulip_conf_path")
    keys, _stderr, status = Open3.capture3("/usr/bin/crudini", "--get", "--", zulip_conf_path, section)
    if status.success?
      filtered_keys = keys.lines.map { |l| l.strip }.select { |l| l.start_with?(prefix) }
      all_values = []
      filtered_keys.each do |key|
        values, _stderr, success = Open3.capture3("/usr/bin/crudini", "--get", "--", zulip_conf_path, section, key)
        if status.success?
          all_values += values.strip.split(/,\s*/)
        end
      end
      return all_values
    else
      return []
    end
  end
end
