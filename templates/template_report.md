# Standard Resource Assessment Workflow
New batch run resource assessment workflowd are needed for twl and avg water level resources. Many parts of this work flow is identical to the current batch run workflows. However, there are a few additional stesps. 

## Inputs:
The new work requires the following inputs:


1. Water level data - directory containing data for each like, same as current batch run workflow. (Note: for twl resources this will be a directory containing TWL data, for an avg waterlevel resource this will be a directory containing avg data).

2. Resource data following the default avg or twl template. The `new_template_batch_run_avg.xlsx` and `new_template_batch_run_twl.xlsx` show required changes, including: addition of new keys, renaming of keys, reorganization of key-value pairs, changes to default values, etc.

Note: This should be the new default pattern, but should not break existing analyses using the current input xlsx files.

## Outputs
The new workflows must produce the following, outputs:

1. Same standard output datafiles, grids and plots. For example standard, `config.metric_mode`-`resources.plot_threshold` _plot.png and _grid.csv outputs (i.e., for twl resources same {save_point_ID}_{elevation_NAVD88_in_ft}_{runup_value_in_ft}_plot.png, and {save_point_ID}_{elevation_NAVD88_in_ft}_{runup_value_in_ft}_grid.csv outputs from long tail point analysis).

2. Output report - new output discussed below. This output should be placed alongside the other outputs for the row being run. It should be name as follows: {config.output_filename_pattern}_report.md

3. A readme.txt - like the current workflows.

Note: If the input data is `{config.elevation_datum}`=IGLD85 and/or the units are in {`config.units}` all outputs, filenames etc. must perform the same IGLD85 to NAVD and/or the m to ft conversions performed for the longtail point analyses.

## New Analysis in the workflow
The new workflows require several new steps:

1. **`annual_probability` assessment** 
    
    The typical AVG and TWL row assessments produce `{config.output_filename_pattern}_grid.csv` and `{config.output_filename_pattern}_plot.png` output files where the grid values are in the specified `frequency_type` units. The new workflow requires that these output files be produced in `annual_probability` units. If the `frequency_type` in the input excel sheet is set to something other than `annual probability` then output files in these units will be named: `{config.output_filename_pattern}_{config.frequency_type}-grid.csv` and `{config.output_filename_pattern}_{config.frequency_type}-plot.png`, repectively. The `annual probability`outputs, with the typical `{config.output_filename_pattern}_grid.csv` and `{config.output_filename_pattern}_plot.png` output filenames, will plot the same outputs, where the grid values and `plotting_threshold` have been transformed into `annual_probability` values.

2. **Runup Assessment (for TWL resources only)** 

    A runup assessment, follows the same logic as the analysis used to produe the typical `{config.output_filename_pattern}_plot.png` and  `{config.output_filename_pattern}_grid.csv` outputs EXCEPT the analysis is performed on the *runup adjusted magnitude* instead of the typical `{resources.magnitude_value}`. The *runup adjusted magnitude* = `{resources.magnitude_value}` - *runup_value*. In this way the analysis used to produce the typical `{config.output_filename_pattern}_plot.png` and  `{config.output_filename_pattern}_grid.csv` outputs, can be viewed as a special case of a runup assessment wher the *runup_value* = 0.    

    The following control flow logic controls how many runup assessments are performed for each row in the `resources` worksheet. IF:

    - IF `min_runup` = `max_runup` = 0: THEN no runup assessment is performed (i.e. only the typical analysis where *runup_value* = 0 is performed). 

    - IF `min_runup` = `max_runup` $\neq$ 0: THEN a single runup assessment is performed that replaces the typical analysis. In this case the single *runup_value* that is used is the the `min_runup` = `max_runup` value.
    
    - IF `max_runup` > `min_runup`: THEN multiple runup assessments are performed by iterating between the `min_runup` and `max_runup` values in 0.5 m increments. IF `min_runup` + 0.5m $\leq$ `max_runup` THEN only the `min_runup` value and `max_runup` value are assessed.

    In the case that multiple runup assessments are performed for a single row in the `resources` worksheet the multiple `{config.output_filename_pattern}_plot.png` and `{config.output_filename_pattern}_grid.png` outputs are produced for the row, each one will differ in the {*runup_value*} part of their name.

2. **Baseline Likelihood Assessment**

    A categorical baseline likelihood score is assigned to each row in `resources` worksheet.

    To assign this baseline likelihood score the following algorithm is followed.

    1. Identify *baseline_metric* value: The *baseline_metric*, or metric value associated with the (0, 0) climate change scenario is retrieved from the row's `{config.output_filename_pattern}_grid.png`).

        **TWL Resources with Runup Assessments**: note in the case of TWL rows with runup assessments, there will be multiple *baseline_metric* values, one for the no runup case (i.e. *runup_value* = 0), and one for each of the *runup_value*s that are assessed. 

    2. Compute the annualized *probability_baseline_metric*: For AVG rows the annualized *probability_baseline_metric* is the *baseline_metric* value converted to a `annual_probability` `frequency type` if it is not in this form already and the TWL edge case described below does not apply. 
    
        **TWL Resources Edge Case Adjustment(s)** - In the case of TWL resources, the following extra step (2a) must be followed to potentially adjusted the *probability_baseline_metric* value. In the case of TWL resources with runup assessments the extra step (2a) is completed for each of the multiple *baseline_metric* values (as discussed in step 1).

        (2a) *probability_baseline_metric* edge cases: All *baseline_metrics* in TWL assessments must have originally been computed based an ARI value (i.e., the ARI value associated with the `{resources.magnitude_value}` in the TWL input data). Two edge cases must be dealt with to compute the *probability_baseline_metric*: (1) if the `{resources.magnitude_value}` - *runup_value* > the TWL elevation associated with the maximum ARI then the *frequency_baseline_metric* = 0. (2) if the `{resources.magnitude_value}` - *runup_value* < the 1 yr ARI TWL elevation, then the *frequency_baseline_metric* = 1.

    3. Assign "n/a" baseline likelihood score: For resources without runup assessments if the *probability_baseline_metric* = 0, then the baseline likelihood score is "n/a". For resources with runup assessments, if the *probability_baseline_metric* associated the the *max_runup* value = 0, then the baseline liklihood score is "n/a".
    
    4. Compute *probability threshold*: The `{resources.plotting_threshold}` is converted into a *probability_threshold* if it is not already expressed as a `annual_probability` `frequency_type` on the domain [0, 1].

    5. Assign "star_high+" baseline likelihood score: For resources without runup assessments if the *frequency_baseline_metric* is more than double the `frequency_threshold` then a score of "star_high+" is assinged. For resoures with runup assessments if the *frequency_baseline_metric* associated with  the no runup case (i.e. *runup_value* = 0) is more than double the `frequency_threshold` then a score of "star_high+" is assigned.

    6. Assign "high+"

## `annual_probability` and `annual_return_interval` `frequency_type`s

In AVG water level rows, when `frequency_type`= `portion` metric values are computed as follows: `portion` = "successes count" / total time steps in the AVG timeseries. The new `annual_probability` `frequency_type`, will effectively "annualize" the `portion` monthly probability values, such that `annual_probability` = `portion` / 12. Therefore, the `annual_return_interval` = 1 / `annual_probability`. 

In TWL rows, the `annual_probability` metric values are computed as follows: `annual_probability` = 1 / ARI value.

 

    To do so the following variables are computed and used:

    1. the *min_runupmagnitude_adjusted_baseline(s)*:  
    1. **grid_baseline_metric** - the metric value associated with the (0, 0) climate change scenario in the row's `{config.output_filename_pattern}_grid.png`), against:

    1. ARIs,  
    
    2. the `{resources.plot_threshold}` value.

    If the 

    0. n/a
    1. low-
    2. low
    3. low+
    4. med-
    5. med
    6. med+
    7. high-
    8. high
    9. high+
    10. *high+

    One this scale, a score of `n/a` is given when 


# Output Report
## <Resource_name>
## <Component_name>

Properties
---
Lake: <lake_name>
Save point: <save_point_id>
Elevation Threshold: >= <magnitude_value_in_NAVD> (NAVD, ft), <magnitude_value_in_IGLD85> (IGLD85, m)
Runup values: <list_of_run_up_values> or None
---

### Baseline Likelihood of Exceeding Threshold

Average return interval: <computed_baseline_ARI>
Comparision return interval: <threshold>
Baseline likelihood rating: <rating>

### Sensitivity to Lake Level Change




# Baseline Likelihood Assessment 
The baseline likelihood is assesed by comparing the <magnitude_value> from the xlsx configuration file to 
 on a 0-10 point scale
0: n/a
1: low-
2: low
3: low+
4: med-
5: med
6: med+
7: high-
8: high
9: high+
10: *high+

Baseline likelihood ratings (no runup):
- n/a: <magnitude_value> > <computed_elevation> (NAVD, ft) of 1,000 yr average return interval
- low-: <magnitude_value> = <computed_elevation> (NAVD, ft) of 1,000 yr average return interval 
- high+: <magnitude_value> < <computed_elevation> (NAVD, ft) of <threshold> average return interval 
- values between 1-9 are based on equal sized increments between low- and high+
- *high+ is assigned when the frequency of exceeding the threshold is more than the double the probability associated with the <threshold> 

Baseline likelihood ratings (with runup):
- n/a: <magnitude_value> + <max_runup> > 1,000 yr average return interval elevation 
- low-:  <magnitude_value> + <max_runup> = <computed_elevation> (NAVD, ft) of <threshold> average return interval
- high+: <magnitude_value> + <min_runup> < <computed_elevation> (NAVD, ft) of <threshold> average return interval   
- values between 1-9 are based on equal sized runup increments between low- and high+
- *high+ is assigned when the frequency of exceeding the threshold is more than the double the probability associated with the <threshold>
