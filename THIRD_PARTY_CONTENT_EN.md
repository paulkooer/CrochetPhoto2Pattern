# Third-Party Content and Authorization Policy

[简体中文](THIRD_PARTY_CONTENT.md) | **English**

This policy covers third-party photographs, patterns, text, measurements, and other
content used or evaluated by the project. It states the project's conservative acceptance
rules and is not legal advice.

## Core rules

- Searchable, viewable, or downloadable content is not automatically authorized for
  copying, processing, training, evaluation, or redistribution.
- A disclaimer, credit, or promise to remove content after notice does not replace prior
  authorization.
- Copyright in a photograph and the rights of an identifiable subject are checked
  separately. An open license or public-domain statement does not itself prove subject
  consent.
- Do not copy protected pattern prose or pattern images. Public sources may contribute only
  necessary facts, provenance, and structural conclusions.
- When in doubt, do not use the item. Unverified web images remain candidates explicitly
  ineligible for G3.

## “Training” versus current repository use

The current repository has no corpus-ingestion, model-weight update, or fine-tuning pipeline.
[`docs/SOURCES.en.md`](docs/SOURCES.en.md) and
[`tests/test_reference_patterns.py`](tests/test_reference_patterns.py) encode necessary facts
such as stitch counts, dimensions, and round-to-round relationships as deterministic reference
fixtures that challenge generator priors. That is reference validation, not model training.

Keeping only independent facts and newly expressed structural conclusions, without source
images or creative pattern prose, materially reduces publication risk. If a future workflow
actually downloads images or text to train a model, non-public inputs still involve copying,
site terms, license scope, and potentially personal-data processing. It needs a separate legal
basis and provenance review; internal use or hidden training samples are not an automatic
exception.

## G3 photo acceptance

Every photo must be bound to a SHA-256 in the evaluation manifest and have one copyright
basis:

1. self-owned, with an owner-attestation reference;
2. written permission, with a traceable permission or consent reference;
3. open license, with the original asset page, creator or rightsholder, exact license and
   version, license URL, and verification date; or
4. public domain, with the original asset page, status identifier, evidence URL, and
   verification date.

An identifiable person additionally requires self-authorization or documented consent.
Photos of minors do not enter G3 unless guardian authority and applicable requirements can
be reliably verified. A copyright license alone is insufficient where subject authorization
is required.

An open license must cover the actual use and necessary processing. Ambiguous terms, broken
provenance, search-result snippets, reposts without an original source, no-derivatives terms,
or restrictions incompatible with the intended use are not accepted. A release baseline
that may support commercial use does not use non-commercial-only licenses.

## Storage and publication boundaries

- Raw images, consent files, personal data, and identifiable reports stay in access-limited
  local storage. `eval_data/` and `eval_outputs/` are Git-ignored.
- Even when `redistribution_allowed=true`, evaluation images are not committed to the
  repository, wheel, or release. The field records scope; it is not a publication command.
- Public reports use stable case IDs and aggregate metrics, not names, email addresses,
  handles, source images, or consent documents.
- At withdrawal or the end of the retention period, delete source images as agreed and
  retain only a non-personal disposition log.

## Web material and physical trials

Small factual observations from web articles may appear with provenance as external context,
but remain `calibration_allowed=false`. They cannot replace a physical trial bound to this
system's exact pattern hash or automatically change production constants. The internet may
be used to recruit makers; only work that physically crochets the exact generated pattern and
completes [`docs/physical-trials.en.md`](docs/physical-trials.en.md) counts toward G4.

Report rights concerns through the [Notice and Takedown Process](NOTICE_AND_TAKEDOWN_EN.md).
That process limits ongoing risk; it does not retroactively authorize earlier use.
