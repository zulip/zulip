# Connect through a proxy

Some corporate and university networks may require you to connect to Zulip
via a proxy.

## Web

Zulip uses your browser's default proxy settings. To set a custom proxy just
for Zulip, check your browser's instructions for setting a custom proxy for
a single website.

## Desktop

1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the lower left corner.

2. Select the **Network** tab.

### System proxy settings

3. Click **Use system proxy settings**.

4. Restart the Zulip desktop app.

### Custom proxy settings

3. Click **Manual proxy configuration**.

4. Either enter a URL for **PAC script**, or fill out **Proxy rules** and
  **Proxy bypass rules**.

5. Click **Save changes**.

In most corporate environments, your network administrator will provide a
URL for the **PAC script**.

The second most common configuration is that your network administrator has
set up a proxy server for accessing the public internet, but URLs on the
local network must be accessed directly. In that case set **Proxy rules** to
the URL of the proxy server (it may look something like
`http://proxy.example.edu:port`), and **Proxy bypass rules** to cover local URLs
(it may look something like `*.example.edu,10.0.0.0/8`).

If either of those apply, you can skip the rest of this guide. If not, we
document the syntax for **Proxy rules** and **Proxy bypass rules** below.

#### Proxy rules

A semicolon-separated list of `protocolRule`s.

```
protocolRule -> [<protocol>"="]<URLList>
protocol -> "http" | "https" | "ftp" | "socks"
URLList -> comma-separated list of URLs, ["direct://"]
```

Some examples:

* `http=http://foo:80;ftp=http://bar:1080` - Use proxy `http://foo:80`
  for `http://` URLs, and proxy `http://bar:1080` for `ftp://` URLs.
* `http://foo:80` - Use proxy `http://foo:80` for all URLs.
* `http://foo:80,socks5://bar,direct://` - Use proxy `http://foo:80` for
  all URLs, failing over to `socks5://bar` if `http://foo:80` is
  unavailable, and after that using no proxy.
* `http=http://foo;socks5://bar` -  Use proxy `http://foo` for `http://` URLs,
  and use `socks5://bar` for all other URLs.

#### Proxy bypass rules

A comma-separated list of URIs. The URIs can be hostnames, IP address
literals, or IP ranges in CIDR notation. Hostnames can use the `*`
wildcard. Use `<local>` to match any of `127.0.0.1`, `::1`, or `localhost`.
