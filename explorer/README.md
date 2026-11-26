# Policy requirements explorer (prototype)

A static site for people who work in the Government of Canada to find the Treasury Board policy requirements that apply to their role. It reads the labeller's `output/` and lets you:

- **start from a role** ("I'm a manager"), with more specific roles included (Travellers under Employees, Delegated managers under Managers);
- **filter** by instrument type, instrument, wording (must / should / may), or mandatory instruments only, and **search** the text;
- **open an instrument** to see who is responsible for what, where it sits in the policy hierarchy, and all its requirements in order;
- **check the source**: every requirement links to its clause on the TBS website.

The look comes from the [GC Design System](https://design-system.canada.ca/) (Canadian Digital Service) components, loaded from its CDN. English only for now.

## Run it locally

```sh
python explorer/build.py                          # writes explorer/site/data/explorer.json from output/
python -m http.server -d explorer/site 8000       # then open http://localhost:8000
```

`build.py` uses only the standard library. The data file is gitignored; it is rebuilt on every deploy.

## Files

| File | What it is |
| --- | --- |
| `build.py` | joins `output/responsibilities.csv`, `output/instruments.csv`, `output/summary.json` and `data/roles.csv` into one compact JSON file |
| `role_groups.csv` | sorts each role into an audience group (Employees, Managers and executives, ...) for the home page and role list. Add new roles here when you add them to `data/roles.csv`; until then they show under "Other roles" |
| `site/index.html`, `site/app.js`, `site/app.css` | the single-page app (no build step, no framework). Views are routed on the URL hash, so every filtered view is a shareable link |

## Publishing

`.github/workflows/explorer.yml` builds the data and deploys `explorer/site` to GitHub Pages on pushes to `main` that touch `explorer/` or `output/`, and after each run of the daily refresh, so the site follows the data. On pull requests it only checks that the build works.

One-time setup: in the repository's **Settings → Pages**, set **Source** to **GitHub Actions**.

## Ideas for later

- French, from TBS's French pages (the labeller would need to read them too).
- Use the LLM pass's `llm_item_type` (the filter appears automatically once it is populated) to hide entitlements and definitions by default.
- "What changed since…": diff two versions of the output.
- Organization-specific context: which roles exist in my department, who holds them.
