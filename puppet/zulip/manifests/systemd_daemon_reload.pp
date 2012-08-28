class zulip::systemd_daemon_reload {
  exec { 'reload systemd':
    # /run/systemd/system only exists if systemd is the running init
    # system (see sd_booted(3)), as opposed to merely installed, as may
    # be the case in containers.
    command     => 'sh -c "! test -d /run/systemd/system || systemctl daemon-reload"',
    refreshonly => true,
  }
}
