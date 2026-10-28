# Source and release record

- Owner/source: Consumer Financial Protection Bureau, [Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/).
- Documentation: [API](https://cfpb.github.io/api/ccdb/), [fields](https://cfpb.github.io/api/ccdb/fields.html), [release notes](https://cfpb.github.io/api/ccdb/release-notes.html).
- Snapshot retrieved: 28 October 2026. Each retained monthly JSON records its exact query, retrieval time, inclusive start, logical exclusive end and actual inclusive API maximum.
- Coverage: January 2018–June 2026. The original buckets cover 14 product labels over the full period. The model uses six consistently named groups, with no row-level complaint data.
- Rights: CFPB-created website material is generally public domain under its [website privacy and use policy](https://www.consumerfinance.gov/privacy/website-privacy-policy/). Third-party materials retain their own rights. This package redistributes factual aggregate counts, not consumer-submitted narrative text. It implies no CFPB endorsement.
- Provenance: [data/manifest.json](data/manifest.json) contains SHA-256 hashes of all 102 retained aggregate snapshots. Source reconciliation checks each month against a separately retrieved whole-period aggregate and tests actual date-boundary behavior.
- Availability limitation: complaints may be published after company response or 15 days. This release does not contain historical publication vintages; imposed feature delays cannot eliminate revision bias.
- Reuse: no new license is asserted over source data. Analysis code, figures and prose remain attributed to James Jean; this repository currently makes them inspectable without granting an additional blanket reuse license.

## Prior work and scope

The [CFPB monthly report series](https://www.consumerfinance.gov/data-research/research-reports/monthly-complaint-report-vol-13/) describes complaint trends. [Vaishnav et al. (2024)](https://arxiv.org/abs/2407.06399) study response prediction and topic modeling. The present study evaluates a different, narrow decision: capacity choice under delayed information and asymmetric costs. This is a scoped comparison, not an exhaustive literature review or a claim of a novel algorithm.
