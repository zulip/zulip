# Connect through a proxy

## Proxy on Desktop App

It's possible to connect to your server through a proxy.
Open the Settings by clicking on the gear icon on the bottom of left sidebar. You can
enter the proxy settings in the `Network` section of Settings.

There are two ways to use proxy -
* Use system proxy settings - This option uses the proxy settings configured on your
  system directly. This option requires restartign the app after toggling.

* Use manual proxy settings - This option allows you to set your own manual settings
  specific for this app.

There are three fields provided in manual settings:
* `PAC script` - The URL associated with the PAC file.

* `Proxy rules` - Rules indicating which proxies to use.

* `Proxy bypass rules` - Rules indicating which URLs should
    bypass the proxy settings.

For a typical setup where internet access is required to use an HTTP proxy,
but URLs on the local network should be accessed directly, configure manual proxy as follows:

`Proxy rules = proxy.example.com:port`

`Proxy bypass rules = *.example.com;10.0.0.0/8`

For more complex setups, read below to configure complex proxy rules and proxy bypass rules.

When `PAC script` and `Proxy rules` are provided together, the `Proxy rules`
option is ignored and `PAC script` configuration is applied.

The `Proxy rules` has to follow the rules below:

```
proxyRules = schemeProxies[";"<schemeProxies>]
schemeProxies = [<urlScheme>"="]<proxyURIList>
urlScheme = "http" | "https" | "ftp" | "socks"
proxyURIList = <proxyURL>[","<proxyURIList>]
proxyURL = [<proxyScheme>"://"]<proxyHost>[":"<proxyPort>]
```

For example:

* `http=foopy:80;socks=foopy2:1080` - Use HTTP proxy `foopy:80` for `http://` URLs, and
  HTTP proxy `foopy2:1080` for `socks://` URLs.
* `foopy:80` - Use HTTP proxy `foopy:80` for all URLs.
* `foopy:80,bar,direct://` - Use HTTP proxy `foopy:80` for all URLs, failing
  over to `bar` if `foopy:80` is unavailable, and after that using no proxy.
* `socks5://foopy:1080` - Use SOCKS v5 proxy `foopy:1080` for all URLs.
* `http=foopy,socks5://bar.com` - Use HTTP proxy `foopy` for http URLs, and fail
  over to the SOCKS5 proxy `bar.com` if `foopy` is unavailable.
* `http=foopy,direct://` - Use HTTP proxy `foopy` for http URLs, and use no
  proxy if `foopy` is unavailable.
* `http=foopy;socks=foopy2` -  Use HTTP proxy `foopy` for http URLs, and use
  `socks4://foopy2` for all other URLs.

The `Proxy bypass rules` is a comma separated list of rules described below:

* `[ URL_SCHEME "://" ] HOSTNAME_PATTERN [ ":" <port> ]`

   Match all hostnames that match the pattern HOSTNAME_PATTERN.

   Examples:
     "foobar.com", "*foobar.com", "*.foobar.com", "*foobar.com:99",
     "https://x.*.y.com:99"

 * `"." HOSTNAME_SUFFIX_PATTERN [ ":" PORT ]`

   Match a particular domain suffix.

   Examples:
     ".google.com", ".com", "http://.google.com"

* `[ SCHEME "://" ] IP_LITERAL [ ":" PORT ]`

   Match URLs which are IP address literals.

   Examples:
     "127.0.1", "[0:0::1]", "[::1]", "http://[::1]:99"

*  `IP_LITERAL "/" PREFIX_LENGHT_IN_BITS`

   Match any URL that is to an IP literal that falls between the
   given range. IP range is specified using CIDR notation.

   Examples:
     "192.168.1.1/16", "fefe:13::abc/33".

*  `<local>`

   Match local addresses. The meaning of `<local>` is whether the
   host matches one of: "127.0.0.1", "::1", "localhost".
