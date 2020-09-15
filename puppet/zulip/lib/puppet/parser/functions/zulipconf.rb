module Puppet::Parser::Functions
  newfunction(:zulipconf, :type => :rvalue, :arity => -2) do |args|
    default = args.pop
    joined = args.join(" ")
    zulip_conf_path = lookupvar('zulip_conf_path')
    output = `/usr/bin/crudini --get #{zulip_conf_path} #{joined} 2>&1`; result=$?.success?
    if result
      output.strip()
    else
      default
    end
  end

  newfunction(:zulipconf_keys, :type => :rvalue, :arity => 1) do |args|
    zulip_conf_path = lookupvar('zulip_conf_path')
    output = `/usr/bin/crudini --get #{zulip_conf_path} #{args[0]} 2>&1`; result=$?.success?
    if result
      return output.lines.map { |l| l.strip }
    else
      return []
    end
  end

  newfunction(:zulipconf_nagios_hosts, :type => :rvalue, :arity => 0) do |args|
    section = "nagios"
    prefix = "hosts_"
    ignore_key = "hosts_fullstack"
    zulip_conf_path = lookupvar('zulip_conf_path')
    keys = `/usr/bin/crudini --get #{zulip_conf_path} #{section} 2>&1`; result=$?.success?
    if result
      keys = keys.lines.map { |l| l.strip }
      filtered_keys = keys.select { |l| l.start_with?(prefix) }.reject { |k| k == ignore_key }
      all_values = []
      filtered_keys.each do |key|
        values = `/usr/bin/crudini --get #{zulip_conf_path} #{section} #{key} 2>&1`; result=$?.success?
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
