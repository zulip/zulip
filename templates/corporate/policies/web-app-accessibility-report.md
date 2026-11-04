# Zulip Accessibility Conformance Report (ACR)

**WCAG 2.2 Edition**

(Based on VPAT® Version 2.5Rev)

**Name of Product/Version:** [Zulip](https://zulip.com), v. 13.0

**Report Date:** November 2026

**Product Description:** [Zulip](https://zulip.com) is an open-source organized team chat app with
unique [topic-based threading](https://zulip.com/why-zulip/) that combines the best of email and
chat to make remote work productive and delightful. Fortune 500 companies,
[leading open source projects](https://zulip.com/case-studies/rust/), and thousands of other
organizations use Zulip every day. Zulip is the only
[modern team chat app](https://zulip.com/features/) that is designed for both live and asynchronous
conversations.

**Contact Information:** [support@zulip.com](mailto:support@zulip.com)

**Notes:**

As an organized team chat app, Zulip provides users the means to upload media content (image, audio,
and video) as well as the tools to make their content accessible (e.g., providing accessible text
on an image via [the Markdown syntax for images](https://spec.commonmark.org/0.31.2/#images)). Our
report, of course, cannot anticipate ways in which user-contributed content negatively impacts
conformance with WCAG success criteria. See WCAG 2.2 for more details on products that include
[user-contributed content](https://www.w3.org/TR/WCAG22/#conformance-partial).

**Evaluation Methods Used:**

We relied on the following evaluation methods:

* Engineer-led review of the product and its codebase
* Automated accessibility reports from browsers
  (e.g., [Firefox's Accessibility Inspector](https://firefox-source-docs.mozilla.org/devtools-user/accessibility_inspector/))
* A review of
  [open issues with the 'accessibility' label](https://github.com/zulip/zulip/issues?q=is%3Aissue+state%3Aopen+label%3Aaccessibility)
  in our issue tracker. Those issues are mentioned in the associated "Remarks and Explanations"
  column in the Success Criteria table below

Additionally, we have opted to self-evaluate in the harshest light possible. Therefore we have many
more cells below that indicate *Partially Supports* than a more generous self-evaluation might
yield. At Zulip, we consider accessibility a high priority, and we intend to frequently revisit this
report to reflect the advancements we make towards making Zulip more accessible to all users.

## Applicable Standards/Guidelines

This report covers the degree of conformance for the following accessibility standard/guidelines:

| Standard/Guideline | Included In Report |
| --- | --- |
| [Web Content Accessibility Guidelines 2.0](https://www.w3.org/TR/WCAG20/) | **Level A (Yes)**<br>Level AA (No)<br>Level AAA (No) |
| [Web Content Accessibility Guidelines 2.1](https://www.w3.org/TR/WCAG21/) | **Level A (Yes)**<br>Level AA (No)<br>Level AAA (No) |
| [Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/) | **Level A (Yes)**<br>Level AA (No)<br>Level AAA (No) |

## Terms

The terms used in the Conformance Level information are defined as follows:

Supports: The functionality of the product has at least one method that meets the criterion without known defects or meets with equivalent facilitation.

Partially Supports: Some functionality of the product does not meet the criterion.

Does Not Support: The majority of product functionality does not meet the criterion.

Not Applicable: The criterion is not relevant to the product.

Not Evaluated: The product has not been evaluated against the criterion. This can only be used in WCAG Level AAA criteria.

## WCAG 2.2 Report

Note: When reporting on conformance with the WCAG 2.2 Success Criteria, they are scoped for full
pages, complete processes, and accessibility-supported ways of using technology as documented in the
[WCAG 2.2 Conformance Requirements](https://www.w3.org/TR/WCAG22/#conformance).

### Table 1: Success Criteria, Level A

Notes:

| Criteria | Conformance Level | Remarks and Explanations |
| --- | --- | --- |
| [1.1.1 Non-text Content](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.2.1 Audio-only and Video-only (Prerecorded)](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.2.2 Captions (Prerecorded)](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.2.3 Audio Description or Media Alternative (Prerecorded)](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.3.1 Info and Relationships](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.3.2 Meaningful Sequence](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.3.3 Sensory Characteristics](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.4.1 Use of Color](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [1.4.2 Audio Control](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.1.1 Keyboard](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.1.2 No Keyboard Trap](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.1.4 Character Key Shortcuts](https://www.w3.org/TR/WCAG21/) (Level A 2.1 and 2.2) |  |  |
| [2.2.1 Timing Adjustable](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.2.2 Pause, Stop, Hide](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.3.1 Three Flashes or Below Threshold](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.4.1 Bypass Blocks](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.4.2 Page Titled](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.4.3 Focus Order](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.4.4 Link Purpose (In Context)](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [2.5.1 Pointer Gestures](https://www.w3.org/TR/WCAG21/) (Level A 2.1 and 2.2) |  |  |
| [2.5.2 Pointer Cancellation](https://www.w3.org/TR/WCAG21/) (Level A 2.1 and 2.2) |  |  |
| [2.5.3 Label in Name](https://www.w3.org/TR/WCAG21/) (Level A 2.1 and 2.2) |  |  |
| [2.5.4 Motion Actuation](https://www.w3.org/TR/WCAG21/) (Level A 2.1 and 2.2) |  |  |
| [3.1.1 Language of Page](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [3.2.1 On Focus](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [3.2.2 On Input](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [3.2.6 Consistent Help](https://www.w3.org/TR/WCAG22/) (Level A 2.2 only) |  |  |
| [3.3.1 Error Identification](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [3.3.2 Labels or Instructions](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |
| [3.3.7 Redundant Entry](https://www.w3.org/TR/WCAG22/) (Level A 2.2 only) |  |  |
| [4.1.1 Parsing](http://www.w3.org/TR/WCAG20/) (Level A)<br>WCAG 2.0 and 2.1 – Always answer ‘Supports’<br>WCAG 2.2 (obsolete and removed) - Does not apply | Supports | For WCAG 2.0 and 2.1, the September 2023 errata update indicates this criterion is always supported. See the [WCAG 2.0 Editorial Errata](https://www.w3.org/WAI/WCAG20/errata/) and the [WCAG 2.1 Editorial Errata](https://www.w3.org/WAI/WCAG21/errata/). |
| [4.1.2 Name, Role, Value](http://www.w3.org/TR/WCAG20/) (Level A) |  |  |

## Legal Disclaimer (Zulip)

[Zulip Terms of Service](https://zulip.com/policies/terms)
