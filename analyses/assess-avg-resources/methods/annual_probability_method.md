# annual_probability: how often a pattern occurs in a year (avg)

`metric_mode = annual_probability` in the avg resources worksheet reports, per scenario,
the portion of water years in which the component's pattern occurs at least once. It
replaces `return_period` for avg. It is **not a return period**.

## Why not a return period

Hydropattern dropped `return_period` upstream on purpose. Monthly avg lake levels are
strongly persistent, so the occurrences in one record are not independent enough to
support a return-period claim. (The swl workflow keeps `return_period`: swl ARI curves are
true frequency curves, not monthly series.)

## Definition

For one scenario and one component:

```
annual_probability = (complete water years with at least 1 occurrence)
                     / (complete water years whose occurrence count is known)
```

- An **occurrence** is a run of consecutive timesteps in which the component's pattern is
  met (its final success column is 1). Hydropattern calls these "events" in the
  `event_count_lower` / `event_count_upper` columns of the `reporting_details` sheet of
  `<resource>_<component>_summary.xlsx`, which this metric reads. Occurrences are not
  treated as independent events.
- Only complete water years count (the `completeness` column is `complete`); a partial
  first or last water year is left out. Water years follow `first_day_of_water_year`.
- A water year counts as "occurrence" when `event_count_lower >= 1`, as "no occurrence"
  when `event_count_upper == 0`. A water year whose unknown (missing) outcomes leave the
  count undecided (`lower == 0 < upper`) is left out of both numerator and denominator.
- An occurrence belongs to the water year in which it starts.
- The result is in [0, 1]. It is NaN for a scenario with no countable water year.
- `success_pattern = false` rows count occurrences of the (inverted) component as
  hydropattern evaluates it, the same as the `portion` and `percentage` modes.

## Outputs

Per row, alongside hydropattern's own files:

- `<name>_annual_probability.csv`: per scenario, `eligible_water_years`,
  `occurrence_water_years`, `annual_probability`.
- `<name>_grid.csv` and `<name>_plot.png` (if `plot_enabled`): the precipitation x
  temperature response surface of `annual_probability`, built by `great_lakes` (hydropattern
  runs with `portion` and its own plot off, so its grid is not written). The default
  `RdBu` colormap is reversed when `success_pattern` is false, so red means less success.

## Legacy worksheets

A config sheet that still says `metric_mode = return_period` is read as
`annual_probability`, with a warning and a note in the run `README.txt`. Rename the option
in the worksheet.

Implementation: `great_lakes.batch.annual_probability`.
