class kandra::ses_logs {
  include kandra::vector

  $ses_logs_sqs_url = zulipsecret('secrets', 'ses_logs_sqs_url', '')
  $ses_logs_s3_bucket = zulipsecret('secrets', 'ses_logs_s3_bucket', '')

  concat::fragment { 'vector_ses_logs':
    target  => $kandra::vector::conf,
    order   => '50',
    content => template('kandra/vector_ses.toml.template.erb'),
  }
}
