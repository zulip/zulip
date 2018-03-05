from typing import Text
from disposable_email_domains import blacklist

def is_reserved_subdomain(subdomain: Text) -> bool:
    if subdomain in ZULIP_RESERVED_SUBDOMAINS:
        return True
    if subdomain[-1] == 's' and subdomain[:-1] in ZULIP_RESERVED_SUBDOMAINS:
        return True
    if subdomain in GENERIC_RESERVED_SUBDOMAINS:
        return True
    if subdomain[-1] == 's' and subdomain[:-1] in GENERIC_RESERVED_SUBDOMAINS:
        return True
    return False

def is_disposable_domain(domain: Text) -> bool:
    return domain.lower() in DISPOSABLE_DOMAINS

ZULIP_RESERVED_SUBDOMAINS = frozenset([
    # zulip terms
    'stream', 'channel', 'topic', 'thread', 'installation', 'organization', 'realm',
    'team', 'subdomain', 'activity', 'octopus', 'acme', 'push',
    # machines
    'zulipdev', 'localhost', 'staging', 'prod', 'production', 'testing', 'nagios', 'nginx',
    # website pages
    'server', 'client', 'features', 'integration', 'bot', 'blog', 'history', 'story',
    'stories', 'testimonial', 'compare', 'for', 'vs',
    # competitor pages
    'slack', 'mattermost', 'rocketchat', 'irc', 'twitter', 'zephyr', 'flowdock', 'spark',
    'skype', 'microsoft', 'twist', 'ryver', 'matrix', 'discord', 'email', 'usenet',
    # zulip names
    'zulip', 'tulip', 'humbug',
    # platforms
    'plan9', 'electron', 'linux', 'mac', 'windows', 'cli', 'ubuntu', 'android', 'ios',
    # floss
    'contribute', 'floss', 'foss', 'free', 'opensource', 'open', 'code', 'license',
    # intership programs
    'intern', 'outreachy', 'gsoc', 'gci', 'externship',
    # tech blogs
    'engineering', 'infrastructure', 'tooling', 'tools', 'javascript', 'python'])

# Most of this list was curated from the following sources:
# http://wiki.dwscoalition.org/notes/List_of_reserved_subdomains (license: CC-BY-SA 3.0)
# http://stackoverflow.com/questions/11868191/which-saas-subdomains-to-block (license: CC-BY-SA 2.5)
GENERIC_RESERVED_SUBDOMAINS = frozenset([
    'about', 'abuse', 'account', 'ad', 'admanager', 'admin', 'admindashboard',
    'administrator', 'adsense', 'adword', 'affiliate', 'alpha', 'anonymous',
    'api', 'assets', 'audio', 'badges', 'beta', 'billing', 'biz', 'blog',
    'board', 'bookmark', 'bot', 'bugs', 'buy', 'cache', 'calendar', 'chat',
    'clients', 'cname', 'code', 'comment', 'communities', 'community',
    'contact', 'contributor', 'control', 'coppa', 'copyright', 'cpanel', 'css',
    'cssproxy', 'customise', 'customize', 'dashboard', 'data', 'demo', 'deploy',
    'deployment', 'desktop', 'dev', 'devel', 'developer', 'development',
    'discussion', 'diversity', 'dmca', 'docs', 'donate', 'download', 'e-mail',
    'email', 'embed', 'embedded', 'example', 'explore', 'faq', 'favorite',
    'favourites', 'features', 'feed', 'feedback', 'files', 'forum', 'friend',
    'ftp', 'general', 'gettingstarted', 'gift', 'git', 'global', 'graphs',
    'guide', 'hack', 'help', 'home', 'hostmaster', 'https', 'icon', 'im',
    'image', 'img', 'inbox', 'index', 'investors', 'invite', 'invoice', 'ios',
    'ipad', 'iphone', 'irc', 'jabber', 'jars', 'jobs', 'join', 'js', 'kb',
    'knowledgebase', 'launchpad', 'legal', 'livejournal', 'lj', 'login', 'logs',
    'm', 'mail', 'main', 'manage', 'map', 'media', 'memories', 'memory',
    'merchandise', 'messages', 'mobile', 'my', 'mystore', 'networks', 'new',
    'newsite', 'official', 'ogg', 'online', 'order', 'paid', 'panel', 'partner',
    'partnerpage', 'pay', 'payment', 'picture', 'policy', 'pop', 'popular',
    'portal', 'post', 'postmaster', 'press', 'pricing', 'principles', 'privacy',
    'private', 'profile', 'public', 'random', 'redirect', 'register',
    'registration', 'resolver', 'root', 'rss', 's', 'sandbox', 'school',
    'search', 'secure', 'servers', 'service', 'setting', 'shop', 'shortcuts',
    'signin', 'signup', 'sitemap', 'sitenews', 'sites', 'sms', 'smtp', 'sorry',
    'ssl', 'staff', 'stage', 'staging', 'stars', 'stat', 'static', 'statistics',
    'status', 'store', 'style', 'support', 'surveys', 'svn', 'syn',
    'syndicated', 'system', 'tag', 'talk', 'team', 'termsofservice', 'test',
    'testers', 'ticket', 'tool', 'tos', 'trac', 'translate', 'update',
    'upgrade', 'uploads', 'use', 'user', 'username', 'validation', 'videos',
    'volunteer', 'web', 'webdisk', 'webmail', 'webmaster', 'whm', 'whois',
    'wiki', 'www', 'www0', 'www8', 'www9', 'xml', 'xmpp', 'xoxo'])

DISPOSABLE_DOMAINS = frozenset(blacklist)
