# Derived Metrics and Excel Reports

This is an optional offline stage after `analyze` in version 0.7.0. It does not change capture data,
XML conversion rules, or the existing analysis files.

## Run

On the analysis host, use Python 3.8+ and install the optional dependency in
the same interpreter that runs `pmt-capture`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-report.txt
./pmt-capture analyze --run-dir results/run-001 --output analysis/run-001 --report
# Open analysis/run-001-report/逐Core看板.html
```

The `analyze --report` command verifies raw samples and decodes with the exact
XML before evaluating the configured GNR metrics and producing the per-Core
HTML and Excel workbook. The full package supplies an approved XML registry;
for a source checkout or base package pass `--metadata /path/to/pmt.xml`.
`--report-output`, `--report-metrics`, and `--report-topology` customize this
stage. Analyzing without `--report` remains standard-library-only. To rerun
only the report on an existing analysis, use:

```bash
./pmt-capture report --analysis-dir analysis/run-001 --output reports/run-001
```

If report generation fails after decoding, the new analysis directory is
retained; resolve the dependency or metric issue and rerun the standalone
`report` command into a new directory. Do not retry `analyze` with the same
output path. No charting runs automatically inside a background capture
process: a separate post-capture analysis step avoids installing XML and
Excel dependencies on the hardware collector host.

The input must contain `decoded.csv`, `analysis.json`, and `provenance/run.json`.
The output must be a new directory outside the input. Failed generation discards
staged output; existing reports are never overwritten. Capture and decoding remain
standard-library-only and keep their existing Python 3.7 minimum.

Outputs:

| File | Content |
| --- | --- |
| `pmt-report.xlsx` | Native Excel charts, partitioned wide Core/Socket/System data, Summary, quality reason counts, Definitions, Chart Data |
| `逐Core看板.html` | Standalone offline viewer: choose aggregator and XML-local Core; seven key trends, up to about 600 actual sample points per slot |
| `core-metrics.csv` | Every configured XML-local core, sample and metric, including excluded values |
| `socket-metrics.csv` | Confirmed mapped cores only; omitted without a usable socket mapping |
| `system-metrics.csv` | Observed slots except explicitly disabled cores |
| `metric-summary.csv` | Per-scope aggregates, sample statistics and excluded counts |
| `metric-quality.csv` | Per-scope/metric quality reason counts, including valid, provisional and excluded rows |
| `metrics.json`, `topology.csv` | Frozen configuration and optional supplied core mapping |
| `report.json` | Input/output fingerprints, implementation fingerprint and provenance |

Core/Socket/System CSV rows retain each observation's quality, notes, numerators,
denominators, actual interval timestamps, member counts and region timestamp skew.
`metric-quality.csv` groups row counts by level, scope, metric and quality; it does
not duplicate the large detail tables. Blank values are unavailable, not zero. Excel charts
reference worksheet cells and cache plotted values; formulas are evaluated by the
report engine, not by Excel. Re-run the report after changing JSON configuration.
Core line charts select up to six representative local cores, one per aggregator
when available. Chart points are capped at 1200 per series; the workbook's wide
data and CSV retain every interval. Excel wide data splits into numbered sheets
before the 1,048,576-row limit, while its Quality sheet summarizes counts of
reasons per scope/metric. Per-row reasons and notes remain in the level CSVs.
The HTML embeds only temperature, experimental usage increase, PVP64/PVP1024
rates, all-bucket frequency/voltage estimates and C6 share. All configured
metrics, including individual histogram buckets, remain in CSV and Excel.

Derived Core rows are streamed one sequence at a time and per-series statistics
are staged in a temporary SQLite database, removed after generation. The
decoded CSV must be ordered by increasing sequence, as produced by `analyze`;
out-of-order inputs fail explicitly. A 600-sample/six-aggregator synthetic
decoded run (10,828,800 Core rows) completed on the offline development host;
the final report stage took 7 min 42 sec and peaked at approximately 888 MiB RSS
with Python 3.14. The Core CSV was 2.6 GiB, the quality-count CSV 1.3 MiB,
and the standalone HTML 70 MiB. This measures reporting from synthetic decoded
data, not capture or raw-to-XML decoding. Plan for several gigabytes of report
output plus SQLite staging and validate the entire
pipeline with real long-running raw data on the intended offline host.

## Metric Configuration

`--metrics config/metrics-gnr.json` is the default. Format `pmt-metrics/v1` matches
the exact CORE GUID `0x22473996` and 14496-byte inventory regions. It currently
defines 64 XML slots per region; this is not a physical enabled-core count.
It does not implement arbitrary expression execution or metrics for other GUIDs.

Each metric has an `id`, `title`, `unit`, `source`, `operation`, `spatial` and
human-readable `formula`. Sources use full decoded group-qualified XML names,
with `{core}`, `{bucket}`, `{pair}`, `{pair_next}` or `{quad0}` through `{quad3}`.
The engine uses `operation` and its parameters; `formula` is documentation.

| Operation | Per-window computation | Default use |
| --- | --- | --- |
| `gauge` | Current value, checked against optional minimum/maximum | Temperature |
| `delta` | Current minus previous, preserving integer subtraction | PVP 64/1024-cycle counts |
| `rate` | Delta divided by actual elapsed seconds | PVP counts/second |
| `histogram_share` | 100 * selected bucket deltas / all bucket deltas | C6 share |
| `histogram_mean` | Sum of selected deltas * weights / selected deltas | Non-C6 frequency estimate |
| `histogram_distribution` | Expand all buckets into individual shares | Frequency/voltage distributions |

Histograms require `buckets`; shares/means use `selected`, means use `weights`,
distributions use `labels`. Optional `invalid_values` identify poison markers;
`provisional` carries unresolved semantic limitations into every output.
`charts` entries select a metric ID (or distribution prefix), title, unit and
`line` or `stacked_column` type.

The GNR configuration also includes dashboard-style Core usage lifetime/interval
increase (experimental U64.38.26 counter, not CPU utilization), all-bucket
frequency mean (C6 r0 at 0 MHz), all-bucket voltage mean (r0 below 602 mV),
and temperature histogram shares. Those use adjacent captured samples, **not**
the live dashboard's rolling 5-minute Prometheus `increase`/`rate` window.
The interactive viewer shows all configured Core slots, including unknown or
zero-only slots; zero alone never proves the physical Core is disabled. It
selects actual samples at a fixed stride and retains the last sample, without
interpolating skipped intervals.

Spatial aggregation is explicit: temperature uses `max`, PVP uses `sum`, and
histograms use `ratio`, recomputing pooled numerators/denominators rather than
averaging percentages. Summary `aggregate` sums deltas, time-weights rates,
denominator-weights histograms, and sample-averages gauges. Its other statistics
(`mean`, `p95`, etc.) describe valid per-window values. Temperature rollup therefore
means a per-window maximum; its temporal aggregate is the mean of these maxima.

The first counter observation is a baseline. Missing inputs, sequence gaps,
elapsed time above `max_gap_factor * IntervalSeconds`, non-increasing timestamps,
counter declines, missing/stale heartbeat and changes in `AGG_DATA_LOSS_COUNT`
exclude affected windows. No reset or wrap is guessed. Missing snapshots at
otherwise observed sequences are explicit; completely absent sequences are
detected at the next observation, not synthesized into the chart. First-sample
gauges carry `freshness_unchecked_first_sample`. Partial rollups expose
`valid_members / expected_members` for the supplied/observed set, not certification
of complete physical platform coverage. A full-size run may generate large
CSV and Excel files; verify free disk space before offline analysis.

## Physical Topology

`report --topology` uses a core-level mapping, distinct from `analyze --topology`:

```csv
endpoint,aggregator,core,socket,die,physical_core,enabled
example-host,telem9,0,0,0,0,true
```

This is a format example, not an asserted mapping for any platform. Supply confirmed
identities from platform documentation or validated topology data. `core` is the
XML-local slot; `enabled` is exactly `true` or `false`. Duplicate PMT identities
and duplicate enabled physical identities are rejected. Explicitly disabled slots
are excluded from rollups; unmapped slots remain in System with unknown-enabled
notes and do not appear in Socket. Zero counters do not establish a disabled core.

## Interpretation Limits

- Histogram time scaling is not yet verified against wall time. Shares and
  bucket-midpoint frequency are provisional, not calibrated utilization or
  instantaneous clock measurements. Open-ended frequency bins use approximate
  representative values from the JSON; XML output is not silently rescaled.
- Voltage bucket r0 is below 602 mV, not C6. The voltage distribution is not
  an active-only voltage calculation. Frequency r0 denotes C6.
- PMT regions are read sequentially, not atomically. System combines observations
  with different timestamps and records the skew.
- Input hashes establish artifact consistency, not independent hardware truth or
  a new raw-to-CSV decode. Finite values do not certify hardware health.
