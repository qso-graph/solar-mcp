# NOAA SWPC responses, recorded

The same files as `qso-graph-desktop/tests/fixtures/noaa/`, so both sides are
held to the same bytes and a change on either is caught (qso-graph/solar-mcp#28).
Recorded from `https://services.swpc.noaa.gov` on 2026-10-11. NOAA's data is a
work of the US government and in the public domain.

- `quiet/`: the three responses as NOAA sent them — `products/summary/10cm-flux.json`,
  `products/noaa-planetary-k-index.json` and `products/noaa-scales.json`.
- `storm/`: the same three, edited to exercise the storm paths: the last Kp raised
  to 5.67, the flux to 168, and the G scale to 2 (moderate). Edited, not recorded.

`expected.json` is what `SolarClient.conditions()` reports for those exact files.
QSO Graph Desktop's Conditions card is tested against the same values, so
solar-mcp stays the specification for the card's behaviour (`QGD-HOM-0008`).

**The three NOAA response files are byte-identical to QSO Graph Desktop's and
must stay so.** Their SHA-256 sums are asserted by `test_fixtures_noaa.py`, so a
careless edit here is caught; an edit on the Desktop side is not, and the pair
has to be updated together.

`expected.json` is *not* byte-identical, and deliberately: Desktop's copy
records `"noaa_g_scale": "2"` for the storm case, which is the defect #28 fixes
— a non-zero level left as a bare digit. The card already showed `G2`, so this
change makes the two agree. The note in Desktop's README describing that as "one
known difference" is what retires when its copy is updated.

`a_index` is reported by solar-mcp since #28 and is not in `expected.json`: the
comparison is over the keys `expected.json` declares, so either side may report
more without breaking the other.
