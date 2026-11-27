import {run} from "@zootools/email-spell-checker";

// A short list avoids "fixing" real domains that look like a short provider name.
const SUGGESTED_DOMAINS = ["gmail.com", "icloud.com", "googlemail.com", "rediffmail.com"];

// Return the email with a corrected domain, or undefined if no typo is likely.
export function get_email_suggestion(raw_email: string): string | undefined {
    const email = raw_email.trim();
    const suggestion = run({
        email,
        domains: SUGGESTED_DOMAINS,
        // The library's list of endings is incomplete and would "fix" valid ones like .co.in.
        topLevelDomains: [],
        // Fix typos of these names on any ending.
        secondLevelDomains: ["yahoo", "hotmail", "outlook"],
    });
    if (suggestion === undefined) {
        return undefined;
    }
    // The library lowercases everything; keep what the user typed before the "@".
    const local_part = email.slice(0, email.lastIndexOf("@"));
    return `${local_part}@${suggestion.domain}`;
}
