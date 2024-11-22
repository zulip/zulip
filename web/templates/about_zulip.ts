import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_about_zulip(context) {
    const out = html`<div
        id="about-zulip"
        class="overlay flex"
        tabindex="-1"
        role="dialog"
        data-overlay="about-zulip"
        aria-hidden="true"
    >
        <div class="overlay-content overlay-container">
            <button type="button" class="exit" aria-label="${$t({defaultMessage: "Close"})}">
                <span aria-hidden="true">&times;</span>
            </button>
            <div class="overlay-body">
                <div class="about-zulip-logo">
                    <a target="_blank" rel="noopener noreferrer" href="https://zulip.com"
                        ><img
                            src="../../static/images/logo/zulip-org-logo.svg"
                            alt="${$t({defaultMessage: "Zulip"})}"
                    /></a>
                </div>
                <div class="about-zulip-version">
                    <strong>Zulip Server</strong>
                    <div class="zulip-version-info">
                        <span
                            >${$t(
                                {defaultMessage: "Version {zulip_version}"},
                                {zulip_version: context.zulip_version},
                            )}</span
                        >
                        <span
                            class="copy-button tippy-zulip-tooltip zulip-version"
                            data-tippy-content="${$t({defaultMessage: "Copy version"})}"
                            data-tippy-placement="right"
                            data-clipboard-text="${context.zulip_version}"
                        >
                            <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                        </span>
                    </div>
                    ${to_bool(context.is_fork)
                        ? html`
                              <div class="zulip-merge-base-info">
                                  <span
                                      >${$t(
                                          {
                                              defaultMessage:
                                                  "Forked from upstream at {zulip_merge_base}",
                                          },
                                          {zulip_merge_base: context.zulip_merge_base},
                                      )}</span
                                  >
                                  <span
                                      class="copy-button tippy-zulip-tooltip zulip-merge-base"
                                      data-tippy-content="${$t({defaultMessage: "Copy version"})}"
                                      data-tippy-placement="right"
                                      data-clipboard-text="${context.zulip_merge_base}"
                                  >
                                      <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
                                  </span>
                              </div>
                          `
                        : ""}
                </div>
                <p>
                    Copyright 2012–2015 Dropbox, Inc., 2015–2021 Kandra Labs, Inc., and
                    contributors.
                </p>
                <p>
                    Zulip is
                    <a
                        target="_blank"
                        rel="noopener noreferrer"
                        href="https://github.com/zulip/zulip#readme"
                        >open-source software</a
                    >, distributed under the Apache 2.0 license.
                </p>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
