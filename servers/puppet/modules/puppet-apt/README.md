# Apt module for Puppet

**Manages apt configuration under Debian or Ubuntu.**

This module is provided by [Camptocamp](http://www.camptocamp.com/)

## Classes

 * apt
 * apt::backports
 * apt::clean
 * apt::params
 * apt::unattended-upgrade
 * apt::unattended-upgrade::automatic

### apt::clean

Variables

 * **$apt\_clean\_minutes**: cronjob minutes  - default uses fqdn\_rand()
 * **$apt\_clean\_hours**  : cronjob hours    - default to 0
 * **$apt\_clean\_mday**   : cronjob monthday - default uses fqdn\_rand()

## Definitions

  * apt::conf
  * apt::key
  * apt::ppa
  * apt::preferences
  * apt::sources\_list

### apt::conf

    apt::conf{'99unattended-upgrade':
      ensure  => present,
      content => "APT::Periodic::Unattended-Upgrade \"1\";\n",
    } 
 
### apt::key

    apt::key {"A37E4CF5":
      source  => "http://dev.camptocamp.com/packages/debian/pub.key",
    }

    apt::key {"997D3880":
      keyserver => "keyserver.ubuntu.com",
    }

### apt::ppa

    apt::ppa {'chris-lea':
      ensure => present,
      key    => 'C7917B12',
      ppa    => 'node.js'
    }

### apt::preferences

    apt::preferences {"${lsbdistcodename}-backports":
      ensure   => present,
      package  => '*',
      pin      => "release a=${lsbdistcodename}-backports",
      priority => 400,
    }

### apt::sources\_list

    apt::sources_list {"camptocamp":
      ensure  => present,
      content => 'deb http://dev.camptocamp.com/packages/ etch puppet',
    }

## Contributing

Please report bugs and feature request using [GitHub issue
tracker](https://github.com/camptocamp/puppet-apt/issues).

For pull requests, it is very much appreciated to check your Puppet manifest
with [puppet-lint](https://github.com/camptocamp/puppet-apt/issues) to follow the recommended Puppet style guidelines from the
[Puppet Labs style guide](http://docs.puppetlabs.com/guides/style_guide.html).

## License

Copyright (c) 2012 <mailto:puppet@camptocamp.com> All rights reserved.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

