class zulip::systemd_daemon_reload {
  exec { 'reload systemd':
    command     => 'sh -c "! command -v systemctl > /dev/null || systemctl daemon-reload"',
    refreshonly => true,
  }
}
