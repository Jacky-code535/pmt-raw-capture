# Platform XML

The tool does not contain platform XML. Supply a compatible PMT registry and its referenced schema files as a local directory. Keep the relative paths used by the registry unchanged.

Both XML commands require the registry explicitly:

```bash
./pmt-capture validate-platform --run-dir results/trial-001 \
  --metadata /path/to/xml/pmt.xml
./pmt-capture analyze --run-dir results/trial-001 \
  --metadata /path/to/xml/pmt.xml --output analysis/trial-001
```

The registry must contain an exact GUID and payload-size mapping for every PMT aggregator observed in the run. `validate-platform` reports two separate results:

- `mapping_valid`: every requested GUID/size resolves to existing common, layout and interface files whose XML identities match the registry.
- `valid`: all selected definitions can also be loaded by the built-in decoder.

Each failure includes its stage and selected file paths. Run-scoped validation is the appropriate preflight check for captured data. Validation without `--run-dir` checks every mapping in the selected registry, which may include platforms unrelated to the current host.

## Decoder Scope

- Exact GUID and payload-size matching.
- Little-endian 64-bit sample containers and XML bit ranges.
- Datatype unit labels and transformation formulas with integer-preserving extraction.
- Arithmetic, bitwise operations, bounded shifts and powers, comparisons, conditional expressions, and the XML `sqrt(value)` function.
- No arbitrary calls, attributes, indexing, executable Python, external entity expansion or network fetches.
- Metric names retain `sampleGroup.sampleName`, including counters.
- Layout references use group and sample identity; unqualified references must be unique.
- Fields containing `RESERVED` or `RSVD` are omitted.
- No hardcoded platform-specific metric expansion and no inferred poison-marker rules.

Unsupported or incomplete definitions fail explicitly. Do not guess missing scales, units, bit ranges or transforms. Configure verified invalid values and counter policies separately. A schema-loading pass verifies structural compatibility, not hardware health or every value-dependent formula path.

## Reproducibility

Analysis copies the registry and required schemas into `provenance/xml`, records their content hashes, and records a Git revision when the XML directory is a checkout. The content hashes remain authoritative when files are modified or supplied without Git.

The analysis output therefore contains copies of the XML used. Treat its distribution according to the XML provider's terms. Platform XML, raw captures and generated analysis directories are intentionally excluded from this source package.
