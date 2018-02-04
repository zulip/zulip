include stdlib
info('has_interface_with(\'lo\'):', has_interface_with('lo'))
info('has_interface_with(\'loX\'):', has_interface_with('loX'))
info('has_interface_with(\'ipaddress\', \'127.0.0.1\'):', has_interface_with('ipaddress', '127.0.0.1'))
info('has_interface_with(\'ipaddress\', \'127.0.0.100\'):', has_interface_with('ipaddress', '127.0.0.100'))
info('has_interface_with(\'network\', \'127.0.0.0\'):', has_interface_with('network', '127.0.0.0'))
info('has_interface_with(\'network\', \'128.0.0.0\'):', has_interface_with('network', '128.0.0.0'))
info('has_interface_with(\'netmask\', \'255.0.0.0\'):', has_interface_with('netmask', '255.0.0.0'))
info('has_interface_with(\'netmask\', \'256.0.0.0\'):', has_interface_with('netmask', '256.0.0.0'))

