# This depends on zulip::base having already been evaluated
class zulip::apt_repository {
  apt::source {'zulip':
    location    => 'http://ppa.launchpad.net/tabbott/zulip/ubuntu',
    release     => $zulip::base::release_name,
    repos       => 'main',
    key         => '84C2BE60E50E336456E4749CE84240474E26AE47',
    key_source  => 'https://zulip.com/dist/keys/zulip.asc',
    pin         => '995',
    include_src => true,
  }
}
