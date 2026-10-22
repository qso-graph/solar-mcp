# The band outlook: what Excellent, Good, Fair, Poor and Sporadic mean

`solar_band_outlook` (and `solar_conditions`' `band_outlook`) rate each HF band with a status and
a comment, as `"Good — reliable daytime DX"`. This document says what each status means and how
each band gets one. QSO Graph Desktop's Conditions card grades bands the same way: solar-mcp is the
specification for it, and both are tested against the same recorded NOAA responses.

## There is no standard for these words

No body defines band-condition words. NOAA's Space Weather Prediction Center defines the impact of
a disturbance on its R, S and G scales, not how good a band is. Propagation models (VOACAP, ITU-R
P.533) define usable frequency, signal-to-noise and circuit reliability as numbers for a path from
one place to another. HamQSL's banner (N0NBH) rates four band groups Good, Fair or Poor; its
[FAQ](https://www.hamqsl.com/FAQ.html) says the calculations "take into account the indices,
background radiation, day/night conditions" and "both propagation and noise", and gives a general
reference table, but not the calculation itself.

So the words are defined here, for qso-graph (KI7MT, 2026-10-22), and the thresholds below are
**rules of thumb, not a propagation model**. They take today's solar flux and planetary K index and
nothing about where the operator is or where they are trying to reach.

## The scale

| Status | What it means on the air |
|---|---|
| **Excellent** | Wide open: strong, long-lasting DX openings during the band's usual hours. |
| **Good** | Regular DX openings expected during the band's usual hours. |
| **Fair** | Openings are short, patchy or weak; DX is possible but not dependable. |
| **Poor** | Likely closed for DX, or degraded by absorption and noise. |
| **Sporadic** | Not graded from the indices: the band opens by sporadic-E, and by F2 when the solar flux is high; watch for openings. |

A status is always one of these five words. The comment says why, in a few words.

## How each band is graded

SFI is the 10.7 cm solar flux in solar flux units; K is the planetary K index. A rule is read top
to bottom and the first that holds is the band's status.

| Band | Rule |
|---|---|
| 160m | K ≥ 5: Poor (storm absorption). K ≥ 3: Fair (some noise). Otherwise Good (quiet night conditions). |
| 80m | K ≥ 5: Poor (D-layer absorption and noise). K ≥ 4: Fair (elevated absorption). Otherwise Good (reliable night band). |
| 40m | K ≥ 5: Fair (reduced DX). Otherwise Good (workhorse band, day and night). |
| 30m | Good (transition band, usually open). |
| 20m | SFI ≥ 150: Excellent (strong F-layer, long openings). SFI ≥ 100: Good (reliable daytime DX). Otherwise Fair (shorter openings at low solar flux). |
| 17m | SFI ≥ 120: Good (DX openings likely). SFI ≥ 90: Fair (marginal openings). Otherwise Poor (insufficient ionization). |
| 15m | SFI ≥ 140: Excellent (wide open DX). SFI ≥ 100: Good (daytime openings). SFI ≥ 80: Fair (sporadic openings). Otherwise Poor (band likely closed). |
| 12m | SFI ≥ 150: Good (DX openings around midday). SFI ≥ 120: Fair (brief openings possible). Otherwise Poor (band likely closed). |
| 10m | SFI ≥ 160: Excellent (worldwide DX). SFI ≥ 130: Good (daytime DX openings). SFI ≥ 100: Fair (short openings or sporadic-E). Otherwise Poor (closed except sporadic-E). |
| 6m | Sporadic (watch for Es openings). |

During a geomagnetic storm (K ≥ 5), 20m to 10m keep the status their solar flux gives them and the
comment becomes "degraded by geomagnetic storm".

## What would make it better

A status for a path rather than a band: from the operator's grid to a region, using a propagation
model. That is a separate piece of work.
