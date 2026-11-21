* `POST /bots`: The `interface_type` parameter is now only accepted
  for outgoing-webhook bots; sending it for other bot types returns
  an error. Previously, it was silently ignored for generic and
  incoming-webhook bots, and silently stored on the `Service` row
  for embedded bots.
