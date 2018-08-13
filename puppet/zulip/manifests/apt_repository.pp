# This depends on zulip::base having already been evaluated
class zulip::apt_repository {
  if $zulip::base::release_name == 'stretch' {
    apt::source {'zulip':
      location    =>  'https://packagecloud.io/zulip/server/debian/',
      release     => $zulip::base::release_name,
      repos       => 'main',
      key         => 'E0847BF76A5F64D82ED0A038B97552F31FBFF74F',
      key_source  => 'https://packagecloud.io/zulip/server/gpgkey',
      pin         => '995',
      include_src => false,
    }
  } else {
    apt::source {'zulip':
      location    => 'http://ppa.launchpad.net/tabbott/zulip/ubuntu',
      release     => $zulip::base::release_name,
      repos       => 'main',
      key         => '84C2BE60E50E336456E4749CE84240474E26AE47',
      key_source  => 'https://zulip.org/dist/keys/zulip-ppa.asc',
      pin         => '995',
      include_src => true,
    }
  }
}
