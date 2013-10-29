# To fail the complete compilation, include this class
class common::require_lsbdistcodename inherits common::assert_lsbdistcodename {
	exec { "false # require_lsbdistcodename": require => Exec[require_lsbdistcodename], }
}
