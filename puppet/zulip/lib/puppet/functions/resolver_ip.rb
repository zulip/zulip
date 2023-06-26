require "resolv"

Puppet::Functions.create_function(:resolver_ip) do
  def resolver_ip()
    parsed = Resolv::DNS::Config.default_config_hash()
    if parsed[:nameserver].empty?
      raise 'No nameservers found in /etc/resolv.conf!  Configure one by setting application_server.nameserver in /etc/zulip/zulip.conf'
    end
    resolver = parsed[:nameserver][0]
    if resolver.include?(':')
      '[' + resolver + ']'
    else
      resolver
    end
  end
end
