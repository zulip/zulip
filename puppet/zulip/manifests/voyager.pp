class zulip::voyager {
  include zulip::apt_repository
  include zulip::base
  include zulip::app_frontend
  include zulip::postgres_appdb_tuned
  include zulip::memcached
  include zulip::rabbit
  include zulip::redis
}
