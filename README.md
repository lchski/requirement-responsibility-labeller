# TBS policy requirement responsibility labeller

_Way cooler than it sounds._

## Quick start

The current pipeline is Python (3.10+). It reads policy XML archived by [TBS Policy Hawk](https://github.com/PatLittle/TBS-Policy-Hawk) and writes CSVs to `output/`. Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml`, pinned in `uv.lock`).

```sh
uv sync                                   # creates .venv with the pinned dependencies (and a Python, if needed)
scripts/fetch-hawk.sh                     # sparse checkout of Hawk's XML into data/hawk (run again to refresh)
uv run python -m labeller                 # writes output/*.csv and output/summary.json
uv run pytest                             # unit tests + accuracy on a hand-labelled sample
```

To run the optional LLM pass locally (see below), set your key first:

```sh
export ANTHROPIC_API_KEY=...
uv run python -m labeller.llm             # fills gaps; uses the committed cache, so only new items cost anything
uv run python -m labeller.llm --max-requests 0   # re-apply cached answers only, no API calls
```

To add or upgrade a dependency, use `uv add <package>` or `uv lock --upgrade` and commit both `pyproject.toml` and `uv.lock`.

To browse the output interactively, see the [policy requirements explorer](explorer/README.md) (`explorer/`), a static site published to GitHub Pages.

A GitHub Actions workflow (`.github/workflows/refresh.yml`) does the same every day and commits `output/` when it changes, so the git history of `output/responsibilities.csv` doubles as a record of how responsibilities change.

## Outputs

| File | One row per | Notes |
| --- | --- | --- |
| `output/responsibilities.csv` | itemized responsibility (a leaf clause) | the main table |
| `output/clauses.csv` | clause, including the parent clauses and headings | for rebuilding context |
| `output/instruments.csv` | instrument in Hawk | capture used, hierarchy path, item counts |
| `output/role_review_queue.csv` | actor phrase that didn't match a canonical role | work list for `data/role_aliases.csv` |
| `output/coverage.csv` | instrument TBS lists | newest capture we have vs. the feed date; `is_behind` marks what's missing or out of date |
| `output/summary.json` | run | headline counts |

Key columns in `responsibilities.csv`:

- `id`, `instrument`, `type`, `version`, `version_date`, `source`: which instrument and which capture. `version_date` is the instrument version's date (TBS's "date modified" for HTML captures). `source` is `xml`, `html` (a page in Hawk's archive) or `snapshot` (a per-change capture folder).
- `container`, `container_title`, `anchor`, `parent_anchor`, `topic`: where the item sits. `anchor` is TBS's own clause number (e.g. `4.1.2.1`) when the XML has one, so it is stable across versions; unnumbered legacy items get a positional key like `c6#12`.
- `stem`, `text`: the item, plus the parent clause text it completes ("Ensuring that all communications products are:" + "non-partisan;").
- `actor_raw`: the responsible actor as written. `actor_how`: `self`, `ancestor`, `fill-down` (older layouts only), or `appendix-reference` (an appendix of bare instructions takes the actor of the clause that cites it). `actor_clause`: the anchor the actor came from.
- `role`, `role_parent`, `role_qualifier`: the canonical role. The qualifier keeps whatever narrows it, so "Heads of evaluation designated under subsection 4.3.12 of the policy" is role "Departmental heads of evaluation" with qualifier "designated under subsection 4.3.12 of the policy".
- `modality` (must / should / may), `frequency` (annually, within 30 days...), `other_actors` (in consultation with, approved by...), `links` (ids of instruments the item links to).

## How the Python pipeline works

1. **Index** (`labeller/index.py`): find every usable capture in `data/hawk` and `data/local` (both shaped like Hawk's `data/` folder) and keep the newest version of each instrument. Hawk saved real XML until August 2025. Since then it has mostly saved the HTML page (under `.xml` names) or, when TBS's firewall refused it, a "Request Rejected" page, plus per-change snapshot folders (`<Category>/<id>_<date>/<stamp>.html`). Files are sniffed, not trusted by extension; firewall pages are skipped. For the same version, XML wins over HTML. Only instruments TBS currently lists (Hawk's feed `items.csv`, Hawk's hierarchy CSV, or a scraped `listing.csv` in either root) are kept.
   **Sources** (`labeller/sources.py`): the HTML page is TBS's rendering of the same XML, with every clause number kept as an element id, so it is mapped back onto the XML element names and parsed by the same code. On 162 instruments with both an XML and an HTML capture of the same version, 99.6% of extracted items are identical (key, text and actor); the rest are encoding glitches in the XML or captures that differ in content.
2. **Parse** (`labeller/parse.py`): flatten each chapter and appendix into clauses with parent links. Handles both schema generations: nested `<clause>` elements, and the older `<section>` / `<p>` / `<ul>` / `<h4>` layout. Requirements chapters are found by a title pattern (requirement, responsibilit, procedure, standards), not a fixed list. Appendices are kept when their title says mandatory, standard, requirement or procedure, or when they name an actor.
3. **Actors** (`labeller/actors.py`): an actor statement is recognized by sentence shape ("X is/are responsible for", "X is to", "X must", "X ensures that") and kept only if the subject is a role (its head noun is from a general list: head, officer, manager, secretariat...). Each clause inherits the actor of its nearest ancestor that names one.
4. **Roles** (`labeller/roles.py`): map the actor phrase onto `data/roles.csv` through `data/role_aliases.csv`, by longest alias that is a prefix of the phrase after normalizing case, plurals, parentheticals and "or their delegates". Role ids 1 to 74 are the 2019 actors; later ids were added in 2026.
5. **Enrich** (`labeller/enrich.py`): modality, frequency, secondary actors, links.

### Maintaining roles

When `output/role_review_queue.csv` shows a phrase that should map to a role, add a row to `data/role_aliases.csv` (`alias,role_id`). Add the shortest form that identifies the role: anything after it becomes the qualifier. If it is a new role, add it to `data/roles.csv` first, with `parent_role_id` if it is a subset of an existing role.

### Optional LLM pass

`uv run python -m labeller.llm` (needs `ANTHROPIC_API_KEY`) runs after the rules pipeline and only fills gaps. It has three jobs:

- **Classify** each item as `responsibility`, `entitlement`, `definition`, `criterion` or `context` (`llm_item_type`). Filter on `llm_item_type == "responsibility"` to drop pay entitlements and descriptive text.
- **Fill actors** for items the rules left without one (`llm_actor`, `llm_actor_evidence`, mapped to `llm_role`). It may only choose an actor that the same instrument names in an actor statement, and it has to quote its evidence.
- **Suggest roles** for unmatched actor phrases. These go to `output/role_suggestions.csv` for you to review and copy into `data/role_aliases.csv` or `data/roles.csv`. Nothing is applied automatically.

`role_final` is the rules role where there is one, otherwise the LLM's. `role_source` says which (`rules` or `llm`).

Answers are cached in `data/llm_cache.jsonl`, keyed on a hash of the model, prompt version and item content, and the cache is committed. A scheduled run therefore only sends items that are new or changed. `--max-requests` (default 400, or `LABELLER_LLM_MAX_REQUESTS`) caps each run, and anything over the cap waits for the next run. The model defaults to `claude-haiku-5-5`; set `LABELLER_MODEL` (e.g. `claude-sonnet-5-5`) to use another. By character count, a full first run is about 1.1M input tokens over about 270 requests, which comes to well under $1 on Haiku 5.5. After that, a daily run only sends what changed. Token usage for each run is recorded in `output/summary.json`. On models that support it (Sonnet 5.5, Opus 5.5), requests turn on the API's server-side fallback. A request that ends in a refusal is not cached and is tried again next run.

In GitHub Actions the step runs when the `ANTHROPIC_API_KEY` repository secret is set. Without the secret it still re-applies cached answers, so the `llm_*` columns stay in the output.

### Known limits

- The rules keep items that aren't responsibilities (pay entitlements, definitions, descriptive text in appendices and in some guidelines). On the hand-labelled sample about 30% of items are of this kind. The LLM pass labels them in `llm_item_type`.
- About 17% of items have no actor, mostly appendices written as bare instructions that more than one actor cites.
- `output/coverage.csv` lists instruments TBS lists that have no capture (many are listed only in the hierarchy, so Hawk doesn't watch them) or whose capture is older than the feed date. Fetching those into `data/local` fills the gaps.
- The 31 Directive on Accounting Standards chapters state accounting rules with no actor, so they produce no items.

## Original R version (2019)

The original R scripts are kept for reference. They read Hawk's XML too: run `scripts/fetch-hawk.sh`, then `source("load.R")` in R.

### How the R version worked

1. Policy XML comes from [TBS Policy Hawk](https://github.com/PatLittle/TBS-Policy-Hawk), which archives TBS’s `section=xml` version of each instrument. `scripts/fetch-hawk.sh` checks out just those XML files into `data/hawk`, and `load.R` uses the most recent XML version of each instrument. (The 2019 downloads in `data/policies/` are kept for reference but are no longer read.)
2. [`load.R`](https://github.com/lchski/requirement-responsibility-labeller/blob/master/load.R)
    1. Loads every policy as a string of plaintext.
    2. Breaks the policy into pieces. Tries to do this intelligently, looking at HTML elements. Ultimately we break it down into a sentence level, though lists kinda throw this off.
    3. Checks for the name of each policy, and assigns each row a number.
    4. Manually adds in a few policy requirements/lines that exist only as attributes on `<section>` elements. (Weird stuff.)
    5. Runs `scripts/assign_responsibility.R`.
3. [`scripts/assign_responsibility.R`](https://github.com/lchski/requirement-responsibility-labeller/blob/master/scripts/assign_responsibility.R)
    1. Pulls together the list of ["responsible actors"](https://github.com/lchski/requirement-responsibility-labeller/blob/master/data/responsible_actors.csv) and ["responsible signals"](https://github.com/lchski/requirement-responsibility-labeller/blob/master/data/responsible_signals.csv). Does some pluralizing and concatenating to create our search strings.
    2. Working policy by policy, rolls through the requirements. If a requirement has a string that matches one of the "responsible signals", it marks that requirement as "describing responsibility" (`is_clause_describing_responsibility`). Then, it assigns a "responsible actor" based on the signal/actor combos (`responsible_actor_standardized`).
    3. Notes which clause was the source of the responsible actor for each clause. (Each time we assign responsibility, i.e. where `is_clause_describing_responsibility` is true, we set that clause’s row number as `responsible_clause`. Then we fill down the empty spaces.)

### Unhandled edge cases (2019)

- 23601 (Standard on Web Accessibility): Includes additional requirements in a “Monitoring and reporting requirements” section (chapter 7)
- 25875 (Standard on Web Interoperability): Additional requirements in appendices B–E.
- Responsible description is part of another clause (clause isn't properly split, occurs in a few spots in the policy), maybe a problem in: 27600, Standard on Email Management; 16553, Standard on Geospatial Data; 18909, Standard on Metadata.

Don't show up in the policy hierarchy (added/downloaded manually):

```
12510,"Policy on Privacy Protection"
18309,"Directive on Privacy Practices"
18308,"Directive on Privacy Impact Assessment"
```

### Maybe things to work on (2019)

Sometimes you make responsibility signals that are really just for one policy, like this:

```
"designated senior executive",8,singular,
```

Written for the IM Roles Directive, this could accidentally cast too wide a net elsewhere. Options:

- Leave it as-is, looking to see the impact (does this IM actor show up where it shouldn't?)
- Point it away from the “Departmental Information Management Senior Official” actor, instead at a more generic senior official actor
- Refactor the responsibles code to account for policy-specific signals (cool, but more work!)