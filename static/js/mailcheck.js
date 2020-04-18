/*
 * Mailcheck https://github.com/mailcheck/mailcheck
 * Author
 * Derrick Ko (@derrickko)
 *
 * Released under the MIT License.
 *
 * v 1.1.2
 */

const Mailcheck = {
    domainThreshold: 2,
    secondLevelThreshold: 2,
    topLevelThreshold: 2,

    defaultDomains: ['msn.com', 'bellsouth.net',
                     'telus.net', 'comcast.net', 'optusnet.com.au',
                     'earthlink.net', 'qq.com', 'sky.com', 'icloud.com',
                     'mac.com', 'sympatico.ca', 'googlemail.com',
                     'att.net', 'xtra.co.nz', 'web.de',
                     'cox.net', 'gmail.com', 'ymail.com',
                     'aim.com', 'rogers.com', 'verizon.net',
                     'rocketmail.com', 'google.com', 'optonline.net',
                     'sbcglobal.net', 'aol.com', 'me.com', 'btinternet.com',
                     'charter.net', 'shaw.ca'],

    defaultSecondLevelDomains: ["yahoo", "hotmail", "mail", "live", "outlook", "gmx"],

    defaultTopLevelDomains: ["com", "com.au", "com.tw", "ca", "co.nz", "co.uk", "de",
                             "fr", "it", "ru", "net", "org", "edu", "gov", "jp", "nl", "kr", "se", "eu",
                             "ie", "co.il", "us", "at", "be", "dk", "hk", "es", "gr", "ch", "no", "cz",
                             "in", "net", "net.au", "info", "biz", "mil", "co.jp", "sg", "hu", "uk"],

    run: function (opts) {
        opts.domains = opts.domains || Mailcheck.defaultDomains;
        opts.secondLevelDomains = opts.secondLevelDomains || Mailcheck.defaultSecondLevelDomains;
        opts.topLevelDomains = opts.topLevelDomains || Mailcheck.defaultTopLevelDomains;
        opts.distanceFunction = opts.distanceFunction || Mailcheck.sift3Distance;

        const defaultCallback = function (result) { return result; };
        const suggestedCallback = opts.suggested || defaultCallback;
        const emptyCallback = opts.empty || defaultCallback;

        const result = Mailcheck.suggest(Mailcheck.encodeEmail(opts.email),
                                         opts.domains, opts.secondLevelDomains,
                                         opts.topLevelDomains, opts.distanceFunction);

        return result ? suggestedCallback(result) : emptyCallback();
    },

    suggest: function (email, domains, secondLevelDomains, topLevelDomains, distanceFunction) {
        email = email.toLowerCase();

        const emailParts = this.splitEmail(email);

        if (secondLevelDomains && topLevelDomains) {
        // If the email is a valid 2nd-level + top-level, do not suggest anything.
            if (secondLevelDomains.indexOf(emailParts.secondLevelDomain) !== -1 &&
            topLevelDomains.indexOf(emailParts.topLevelDomain) !== -1) {
                return false;
            }
        }

        let closestDomain = this.findClosestDomain(emailParts.domain, domains,
                                                   distanceFunction, this.domainThreshold);

        if (closestDomain) {
            if (closestDomain === emailParts.domain) {
                // The email address exactly matches one of the supplied domains.
                return false;
            }
            // The email address closely matches one of the supplied domains; return a suggestion
            return { address: emailParts.address, domain: closestDomain, full: emailParts.address + "@" + closestDomain };

        }

        // The email address does not closely match one of the supplied domains
        const closestSecondLevelDomain = this.findClosestDomain(emailParts.secondLevelDomain,
                                                                secondLevelDomains,
                                                                distanceFunction,
                                                                this.secondLevelThreshold);
        const closestTopLevelDomain    = this.findClosestDomain(emailParts.topLevelDomain,
                                                                topLevelDomains, distanceFunction,
                                                                this.topLevelThreshold);

        if (emailParts.domain) {
            closestDomain = emailParts.domain;
            let rtrn = false;

            if (closestSecondLevelDomain && closestSecondLevelDomain
                !== emailParts.secondLevelDomain) {
                // The email address may have a mispelled second-level domain; return a suggestion
                closestDomain = closestDomain.replace(emailParts.secondLevelDomain,
                                                      closestSecondLevelDomain);
                rtrn = true;
            }

            if (closestTopLevelDomain && closestTopLevelDomain !== emailParts.topLevelDomain) {
                // The email address may have a mispelled top-level domain; return a suggestion
                closestDomain = closestDomain.replace(new RegExp(emailParts.topLevelDomain + "$"), closestTopLevelDomain);
                rtrn = true;
            }

            if (rtrn === true) {
                return { address: emailParts.address, domain: closestDomain, full: emailParts.address + "@" + closestDomain };
            }
        }

        /* The email address exactly matches one of the supplied domains, does not closely
     * match any domain and does not appear to simply have a mispelled top-level domain,
     * or is an invalid email address; do not return a suggestion.
     */
        return false;
    },

    findClosestDomain: function (domain, domains, distanceFunction, threshold) {
        threshold = threshold || this.topLevelThreshold;
        let dist;
        let minDist = Infinity;
        let closestDomain = null;

        if (!domain || !domains) {
            return false;
        }
        if (!distanceFunction) {
            distanceFunction = this.sift3Distance;
        }

        for (let i = 0; i < domains.length; i = i + 1) {
            if (domain === domains[i]) {
                return domain;
            }
            dist = distanceFunction(domain, domains[i]);
            if (dist < minDist) {
                minDist = dist;
                closestDomain = domains[i];
            }
        }

        if (minDist <= threshold && closestDomain !== null) {
            return closestDomain;
        }
        return false;

    },

    sift3Distance: function (s1, s2) {
    // sift3: http://siderite.blogspot.com/2007/04/super-fast-and-accurate-string-distance.html
        if (s1 === null || s1.length === 0) {
            if (s2 === null || s2.length === 0) {
                return 0;
            }
            return s2.length;

        }

        if (s2 === null || s2.length === 0) {
            return s1.length;
        }

        let c = 0;
        let offset1 = 0;
        let offset2 = 0;
        let lcs = 0;
        const maxOffset = 5;

        while (c + offset1 < s1.length && c + offset2 < s2.length) {
            if (s1.charAt(c + offset1) === s2.charAt(c + offset2)) {
                lcs = lcs + 1;
            } else {
                offset1 = 0;
                offset2 = 0;
                for (let i = 0; i < maxOffset; i = i + 1) {
                    if (c + i < s1.length && s1.charAt(c + i) === s2.charAt(c)) {
                        offset1 = i;
                        break;
                    }
                    if (c + i < s2.length && s1.charAt(c) === s2.charAt(c + i)) {
                        offset2 = i;
                        break;
                    }
                }
            }
            c = c + 1;
        }
        return (s1.length + s2.length) / 2 - lcs;
    },

    splitEmail: function (email) {
        const parts = email.trim().split('@');

        if (parts.length < 2) {
            return false;
        }

        for (let i = 0; i < parts.length; i = i + 1) {
            if (parts[i] === '') {
                return false;
            }
        }

        const domain = parts.pop();
        const domainParts = domain.split('.');
        let sld = '';
        let tld = '';

        if (domainParts.length === 0) {
            // The address does not have a top-level domain
            return false;
        } else if (domainParts.length === 1) {
            // The address has only a top-level domain (valid under RFC)
            tld = domainParts[0];
        } else {
            // The address has a domain and a top-level domain
            sld = domainParts[0];
            for (let i = 1; i < domainParts.length; i = i + 1) {
                tld += domainParts[i] + '.';
            }
            tld = tld.substring(0, tld.length - 1);
        }

        return {
            topLevelDomain: tld,
            secondLevelDomain: sld,
            domain: domain,
            address: parts.join('@'),
        };
    },

    // Encode the email address to prevent XSS but leave in valid
    // characters, following this official spec:
    // http://en.wikipedia.org/wiki/Email_address#Syntax
    encodeEmail: function (email) {
        let result = encodeURI(email);
        result = result.replace('%20', ' ').replace('%25', '%').replace('%5E', '^')
            .replace('%60', '`').replace('%7B', '{').replace('%7C', '|')
            .replace('%7D', '}');
        return result;
    },
};

// Export the mailcheck object if we're in a CommonJS env (e.g. Node).
// Modeled off of Underscore.js.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Mailcheck;
}

// Support AMD style definitions
// Based on jQuery (see http://stackoverflow.com/a/17954882/1322410)
let define;
if (typeof define === "function" && define.amd) {
    define("mailcheck", [], function () {
        return Mailcheck;
    });
}

if (typeof window !== 'undefined' && window.jQuery) {
    (function ($) {
        $.fn.mailcheck = function (opts) {
            const self = this;
            if (opts.suggested) {
                const oldSuggested = opts.suggested;
                opts.suggested = function (result) {
                    oldSuggested(self, result);
                };
            }

            if (opts.empty) {
                const oldEmpty = opts.empty;
                opts.empty = function () {
                    oldEmpty.call(null, self);
                };
            }

            opts.email = this.val();
            Mailcheck.run(opts);
        };
    }(jQuery));
}


