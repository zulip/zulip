# @summary Adds an iptables "allow" rule for the host for a port.
#
# Rules with the same ordering are ordered by the rule name.
#
define kandra::firewall_allow (
  $port = '',
  $proto = 'tcp',
  $order = '50',
) {
  if $port == '' {
    $portname = $name
  } else {
    $portname = $port
  }

  concat::fragment { "iptables_v4_${portname}":
    target  => '/etc/iptables/rules.v4',
    order   => $order,
    content => "-A INPUT -p ${proto} --dport ${portname} -j ACCEPT -m comment --comment \"${name}\"\n",
  }

  concat::fragment { "iptables_v6_${portname}":
    target  => '/etc/iptables/rules.v6',
    order   => $order,
    content => "-A INPUT -p ${proto} --dport ${portname} -j ACCEPT -m comment --comment \"${name}\"\n",
  }
}
