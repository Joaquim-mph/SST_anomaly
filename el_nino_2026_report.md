# Is 2026 the Strongest El Niño in Decades? A Check Against NOAA Data

*Data through 20 October 2026*

## 1. Introduction

El Niño is when the surface of the central and eastern tropical Pacific gets unusually warm. Scientists measure it mostly in a box of ocean called **Niño 3.4** (5°S–5°N, 170°W–120°W). The usual yardstick is the **anomaly**: how many degrees warmer or cooler the water is than normal for that time of year. Roughly:

| Niño 3.4 anomaly | Usual label |
|---|---|
| +0.5 to +1.0 °C | Weak |
| +1.0 to +1.5 °C | Moderate |
| +1.5 to +2.0 °C | Strong |
| above +2.0 °C | Very strong ("super") |

The El Niños usually counted as the biggest in modern records are **1982–83, 1997–98 and 2015–16**. 2023–24 was also strong.

This report tests one claim: **"The 2026 El Niño is the strongest in decades."** It uses public NOAA data that anyone can download and check.

## 2. Methodology

### Data sources

The checks use three independent NOAA products:

1. **NOAA Coral Reef Watch (CRW) v3.1.** Daily satellite sea surface temperature anomaly maps at 5 km resolution. I downloaded every day from 1 Jan 2025 to 20 Oct 2026 (658 files). I also downloaded the same calendar dates (15 Sep, 1 Oct, 15 Oct, 20 Oct) for 1997, 2015 and 2023.
   - https://www.star.nesdis.noaa.gov/pub/socd/mecb/crw/data/5km/v3.1_op/nc/v1.0/daily/ssta/
2. **NOAA Climate Prediction Center (CPC), OISST-based Niño indices.** Monthly values back to 1982 (`sstoi.indices`) and weekly values back to 1990 (`wksst9120.for`).
   - https://www.cpc.ncep.noaa.gov/data/indices/
3. **CPC Oceanic Niño Index (ONI).** This is NOAA's official index for declaring and ranking El Niños: a 3-month running mean that goes back to 1950. CPC also publishes a **Relative ONI (RONI)**, which subtracts the overall warming of the tropical oceans.
   - https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
   - https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt

### Processing

- From the CRW maps, I computed the average anomaly over Niño 3.4, Niño 3 (5°S–5°N, 150°W–90°W) and Niño 1+2 (10°S–0°, 90°W–80°W). Each grid cell is weighted by its area, so cells near the equator count more than cells farther from it.
- The CPC indices are used as published.
- **Two kinds of comparison:**
  - *Same date:* how 2026 compares with past events at the same point in the calendar.
  - *Peak:* how 2026 so far compares with the **highest values** past events ever reached.

  The second comparison is the harder test, because past events peaked in Nov–Jan and 2026 has not peaked yet.

## 3. Results

### 3.1 Same date (mid-October)

| Source | 1997 | 2015 | 2023 | **2026** |
|---|---|---|---|---|
| CRW Niño 3.4, 20 Oct | +2.35 | +2.48 | +1.75 | **+3.31** |
| CRW Niño 3, 20 Oct | +3.14 | +2.61 | +2.40 | **+4.43** |
| CRW Niño 1+2, 15 Oct | +3.73 | +2.08 | +2.74 | **+5.72** |
| CPC weekly Niño 3.4, 8–21 Oct | +2.05 | +2.25 | +1.55 | **+3.30** |

At this point in the year, 2026 is about **1 °C warmer than 1997 or 2015**, the two benchmark "super" El Niños. Its lead is even larger closer to the South American coast (Niño 1+2).

### 3.2 Monthly Niño 3.4 (CPC OISST, June–September)

| Year | Jun | Jul | Aug | Sep | Event peak |
|---|---|---|---|---|---|
| 1982 | +0.65 | +0.27 | +0.86 | +1.24 | +2.21 (Dec) |
| 1997 | +0.81 | +1.27 | +1.68 | +1.84 | +2.11 (Nov) |
| 2015 | +1.02 | +1.26 | +1.65 | +1.79 | +2.72 (Nov) |
| 2023 | +0.88 | +1.07 | +1.30 | +1.53 | +1.99 (Dec) |
| **2026** | **+1.55** | **+2.03** | **+2.52** | **+2.84** | **still rising** |

**September 2026 (+2.84 °C) is the highest monthly value in the whole record since 1982.** It beats November 2015 (+2.72), the previous record. In other words, 2026 has already passed the *peak* of every earlier event in this dataset, months before El Niños normally peak.

### 3.3 Weekly Niño 3.4 (CPC OISST, since 1990)

| Event | Highest weekly value |
|---|---|
| 1997–98 | +2.3 |
| 2015–16 | +3.0 |
| 2023–24 | +2.1 |
| **2026** | **+3.3 (Oct, still rising)** |

### 3.4 Official 3-month indices (July–September)

| Index | 1997 | 2015 | **2026** | Rank of 2026 |
|---|---|---|---|---|
| ONI (official) | +1.79 | +1.73 | **+2.16** | **1st** since 1950 |
| RONI (relative) | +1.84 | +1.54 | **+1.69** | 2nd, behind 1997 |

### 3.5 Trajectory in this repo's CRW data

Monthly Niño 3.4 averages for 2026: Apr +0.68, May +1.23, Jun +1.76, Jul +2.28, Aug +2.74, Sep +3.01, Oct (to the 20th) +3.21. The value has risen every month with no sign of levelling off.

## 4. Discussion

**What supports the claim.** Three separate NOAA products, built from different processing chains, all put 2026 first:

- by a wide margin at the same calendar date;
- above every earlier event's *all-time peak* in the monthly (since 1982) and weekly (since 1990) OISST series;
- first for July–September in the official ONI since records began in 1950.

**Honest caveats** (these are the points a skeptic could fairly raise):

1. **The event isn't finished.** NOAA's final ranking uses the ONI peak, which normally arrives in Nov–Jan. The marks to beat are **+2.59 (2015–16)** and **+2.37 (1997–98)**. 2026 is at +2.16 for July–September and still climbing, so it is very likely to pass both. Until the winter numbers are in, though, "strongest by peak ONI" is a forecast, not a fact.
2. **Background warming inflates the standard numbers.** The whole tropical ocean is warmer than in the 1980s–90s. Part of every recent anomaly is that general warming, not El Niño itself. The relative index (RONI) removes it, and on RONI 2026 currently ranks **second, behind 1997**, for July–September. So on the strictest measure, the fair statement is "one of the two strongest."
3. **Different datasets use different baselines.** CRW, OISST and ERSST (the dataset behind ONI) each compare against their own reference period, so their numbers aren't identical. That is why this report compares years *within* each dataset and never mixes them. 2026 ranks first within every one except RONI.
4. **Satellite records only go back to the early 1980s.** "In decades" is safe. "Ever" would need older ship-based reconstructions, such as the ONI back to 1950, which also ranks 2026 first so far.

## 5. Conclusion

**The claim holds up.** On NOAA's standard measures, the 2026 El Niño is not only the strongest in decades. It is already the strongest in the satellite era (since 1982), and it has passed the peaks of 1997–98 and 2015–16 even though those events had extra months to build. The one qualification is the relative index, which removes background ocean warming and currently puts 2026 just behind 1997. Even on that measure, 2026 is among the two strongest El Niños of the past 75 years.

If you want to check this yourself, the CPC files linked above are plain text and open in any browser. Look at the `NINO3.4 ANOM` column for September 2026 in `sstoi.indices` and compare it with every other row.
