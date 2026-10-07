# site/app.js and the web app

## Design

The app is a static page styled as a research paper, at the user's request on 2026-10-07: Times New Roman, falling back to the metric-compatible Tinos from Google Fonts where it is not installed (the user asked for Times New Roman on 2026-10-07), a 760-pixel column, an abstract, numbered sections, "Figure n" and "Table n" captions, journal-style tables with horizontal rules only, and references. The user chose a static site over Streamlit so that it needs no server, all 64 strategies, a public GitHub Pages site, and no personal holdings.

Everything is computed in the browser from the snapshot (see `momentum/site_snapshot.py.md`):

| View | How it is computed |
|---|---|
| Holdings in month m | Union of the cohorts formed at m−K to m−1, each 1/K, equal within a cohort; a share in several cohorts adds up |
| Current portfolio | Holdings for the month after the latest formation month |
| Months held | Count back while the share stays in the holdings |
| Joiners and leavers | Holdings in m compared with m−1; a leaver's "last ranked" is the formation month of its most recent cohort |
| Performance, analytics | From `returns.json`, restricted to months from the common start (January 2007), so every number matches the README and the 64-row comparison |

The specification is kept in the URL hash, such as `#j12-k3-skip5-top500`, so any view can be linked.

## Charts

Apache ECharts 5.5.1 from jsDelivr, rendered as SVG, with the page's serif face. Colours follow the dataviz reference palette's first two categorical slots (blue for the portfolio, orange for the index), validated for colour-blind separation in both modes by the palette's documentation; the validator itself could not be run because Node.js is not installed. Heat maps use the palette's blue–red diverging pair with a grey midpoint. Dark mode follows the operating system's setting and redraws the charts when it changes. No chart uses two y-axes: turnover and cost drag were split, with cost drag moved to Table 7.

## Running locally

Browsers refuse to load JSON files from a page opened straight from disk, so `site_server.py` serves the package's `site/` folder on 127.0.0.1 with Python's own `http.server`. The command is registered as `jt-momentum-app` in `pyproject.toml`.

## Publishing

`.github/workflows/pages.yml` uploads `src/jegadeesh_titman_india/site` to GitHub Pages on every push to `main` that changes the site. GitHub Pages is free only for public repositories.
