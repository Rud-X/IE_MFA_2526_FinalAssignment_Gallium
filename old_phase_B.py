"""Archived domestic-production / combination Phase B for the gallium MFA notebook.

This module holds the *superseded* Phase B that built the use-phase inflow by
combining imported finished products with a domestically-manufactured stream
(derived from raw-gallium imports). The notebook (`Rud_Gallium_MFA_3.ipynb`) has
since moved to a stock-driven Phase B that uses imported products only, so this
code is no longer part of the notebook — it is kept here for reference and reuse.

The notebook is not importable, so the functions that depend on notebook helpers
(`build_imp_exp_table`, `translate_to_Ga_MI`, `calculate_flow_driven_MFA`,
`calculate_lifecycle_flows`, ...) take them as explicit arguments. Import this
module and pass the notebook's functions in to run the old pipeline.
"""

import numpy as np
import pandas as pd

# Raw (unwrought) gallium imported into the EU and manufactured domestically into
# finished products. It is NOT a use-phase product itself: it feeds Manufacturing
# (see the domestic-production stream, steps 2-5). Material intensity is ~1.0
# because unwrought gallium is essentially pure gallium, so translate_to_Ga_MI is
# effectively a no-op. The near-zero survival curve (fixed_lifetime of 1 year)
# encodes that raw gallium passes quickly through manufacturing.
RAW_MATERIAL_INFO = {
    "raw_Ga": {
        # "product": [811292],  # "Unwrought gallium; gallium powders"
        "product": [81129289],  # "Unwrought gallium; gallium powders"
        "material_intensity_Ga": 1.0,
        "survival_curve_parameters": {"type": "fixed_lifetime", "lifetime": 1},
    },
}


def calculate_domestic_use_inflow(
    eurostat_df,
    raw_info,
    lifecycle_stages_names,
    build_imp_exp_table,
    translate_to_Ga_MI,
    calculate_flow_driven_MFA,
    manuf_stage=5,
    use_stage=7,
    show_output=False,
):
    """Derive the domestic (non-product-specific) use-phase inflow from raw gallium imports.

    Raw (unwrought) gallium is imported, passes quickly through Manufacturing,
    and the resulting finished products flow into the Use phase. This reuses the
    generic flow-driven MFA, anchored at Manufacturing with a near-zero survival
    curve, then applies the Manufacturing->Use transfer coefficient.

    Process:
    1. Build the raw gallium import/export table (kg) for the raw product code.
    2. Translate to gallium mass (raw gallium MI ~ 1.0, so effectively a no-op).
    3. Run the flow-driven MFA anchored at Manufacturing using the near-zero
       survival curve from raw_info (raw Ga passes quickly through manufacturing).
    4. Read the Manufacturing->Use transfer coefficient from lifecycle_stages_names.
    5. Return the manufacturing outflow scaled by that TC as a TIME_PERIOD /
       Net_Flow_kg table, so it plugs straight into the existing helpers.

    Args:
        eurostat_df: COMEXT-format DataFrame (as used by build_imp_exp_table).
        raw_info: Dict for the raw material with keys "product",
            "material_intensity_Ga", and "survival_curve_parameters"
            (e.g. RAW_MATERIAL_INFO["raw_Ga"]).
        lifecycle_stages_names: Dict of lifecycle stages; used to read the
            Manufacturing->Use transfer coefficient.
        build_imp_exp_table: Notebook helper that builds the import/export table.
        translate_to_Ga_MI: Notebook helper that scales a table by a material intensity.
        calculate_flow_driven_MFA: Notebook helper that runs the flow-driven MFA.
        manuf_stage: Stage number of Manufacturing. Defaults to 5.
        use_stage: Stage number of Use. Defaults to 7.
        show_output: Whether calculate_flow_driven_MFA should plot its
            intermediate matrices/curves. Defaults to False.

    Returns:
        tuple:
        - pd.DataFrame: Historical-only table with columns "TIME_PERIOD" and
          "Net_Flow_kg", the domestic gallium flow into the Use phase.
        - pd.DataFrame: the raw gallium import/export table.
    """
    # 1. Build the raw gallium import/export table (kg)
    raw_imp_exp = build_imp_exp_table(eurostat_df, raw_info["product"])
    # 2. Translate to gallium mass (MI ~ 1.0 => effectively a no-op)
    raw_imp_exp_Ga = translate_to_Ga_MI(raw_imp_exp, raw_info["material_intensity_Ga"])
    # 3. Flow-driven MFA anchored at Manufacturing with the near-zero survival curve
    manuf_mfa = calculate_flow_driven_MFA(
        raw_imp_exp_Ga,
        show_output=show_output,
        survival_curve_parameters=raw_info["survival_curve_parameters"],
    )
    # 4. Manufacturing -> Use transfer coefficient
    tc = lifecycle_stages_names[manuf_stage]["TC_output"][use_stage]
    # 5. Scale manufacturing outflow by the TC and return as a TIME_PERIOD / Net_Flow_kg table
    domestic_use_inflow = pd.DataFrame(
        {
            "TIME_PERIOD": manuf_mfa.index.astype(int),
            "Net_Flow_kg": manuf_mfa["outflows [kg/year]"].to_numpy() * tc,
        }
    ).reset_index(drop=True)
    return domestic_use_inflow, raw_imp_exp


def calculate_use_phase_split(import_inflows):
    """Compute the per-year use-phase split between product categories from import inflows.

    Because the inflow basis is Net_Flow_kg (Imports - Exports), a product can
    have a negative net flow in net-exporter years. A share of a negative flow is
    not meaningful, so negative years are floored to 0: the split is the share of
    each product among the *positive* use-phase additions in that year.

    Process:
    1. Collect every product's Net_Flow_kg into a year-indexed frame; treat
       missing product-years as 0 and floor negative (net-export) years to 0.
    2. Sum across products to get the total positive inflow per year.
    3. Divide each product by the total to get its per-year share in [0, 1].
       Years with no positive inflow (no basis for a split) carry the split from
       the nearest year with data (forward/back fill) so it always sums to 1 and
       mass is conserved when the split is applied to the domestic inflow.

    Args:
        import_inflows: Dict mapping product name to a TIME_PERIOD / Net_Flow_kg
            table (e.g. the per-product import inflows from step 1).

    Returns:
        pd.DataFrame: Indexed by year (TIME_PERIOD), one column per product,
        holding that product's fraction of the total positive use-phase inflow
        (each row in [0, 1], summing to 1 once any year has data).
    """
    # 1. Collect each product's inflow; missing years -> 0, net-export years -> 0
    inflow_by_product = (
        pd.DataFrame(
            {
                prod: table.set_index("TIME_PERIOD")["Net_Flow_kg"]
                for prod, table in import_inflows.items()
            }
        )
        .fillna(0.0)
        .clip(lower=0.0)
    )
    # 2. Total positive inflow across products per year
    total = inflow_by_product.sum(axis="columns")
    # 3. Per-product fraction in [0, 1]; carry the split from the nearest year
    #    with data into empty (no positive inflow) years so it always sums to 1.
    split_df = inflow_by_product.div(total, axis="index")  # 0/0 -> NaN for empty years
    split_df = split_df.ffill().bfill().fillna(0.0)
    return split_df


def apply_use_phase_split(domestic_use_inflow, split_df, override_split=None):
    """Split the single domestic use-phase inflow into the product categories.

    Process:
    1. Pick the split to apply: a scenario override if given, otherwise the
       import-derived split.
    2. Take the domestic inflow as a year-indexed series.
    3. Multiply the domestic inflow by each product's per-year share, carrying the
       split into any years outside the split's range (forward/back fill) so the
       domestic inflow is fully attributed and mass is conserved.

    Args:
        domestic_use_inflow: TIME_PERIOD / Net_Flow_kg table for the total
            domestic use-phase inflow (from calculate_domestic_use_inflow).
        split_df: Per-year split DataFrame (year x product) from
            calculate_use_phase_split.
        override_split: Optional DataFrame in the same shape as split_df used to
            override the domestic split (e.g. for scenarios where the domestic
            mix differs from the import mix). Defaults to None.

    Returns:
        dict: Mapping product name to a TIME_PERIOD / Net_Flow_kg table holding
        the domestic use-phase inflow attributed to that product.
    """
    # 1. Choose the split to apply (scenario override or import-derived)
    split = override_split if override_split is not None else split_df
    # 2. Year-indexed domestic inflow series
    domestic = domestic_use_inflow.set_index("TIME_PERIOD")["Net_Flow_kg"]
    # 3. Multiply by each product's per-year share (fill years outside the split's
    #    range from the nearest known split so domestic mass is fully attributed)
    domestic_inflows = {}
    for prod in split.columns:
        share = split[prod].reindex(domestic.index).ffill().bfill().fillna(0.0)
        product_series = (domestic * share).rename("Net_Flow_kg")
        product_df = product_series.reset_index()
        product_df.columns = ["TIME_PERIOD", "Net_Flow_kg"]
        domestic_inflows[prod] = product_df
    return domestic_inflows


def combine_use_inflows(import_inflows, domestic_inflows):
    """Sum import and domestic use-phase inflows and compute the import-split time-series.

    The combined inflow keeps the Net_Flow_kg basis (so it may be negative in
    net-exporter years). The import split, however, is consumed downstream as a
    lifecycle import_share and must lie in [0, 1]; it is therefore clamped, with
    net-export / zero-total years treated as fully domestic (share 0).

    Process:
    1. For each product, align the import and domestic inflows on year and sum
       them into the total (Net_Flow_kg) use-phase inflow.
    2. Compute the per-year import split = positive imports / positive total,
       clamped to [0, 1] (guarding divide-by-zero / net-export years => 0).
    3. Return the combined inflows and the import-split series per product.

    Args:
        import_inflows: Dict mapping product to a TIME_PERIOD / Net_Flow_kg table
            of imported finished-product inflows (step 1).
        domestic_inflows: Dict mapping product to a TIME_PERIOD / Net_Flow_kg
            table of domestically produced inflows (step 4).

    Returns:
        tuple:
        - total_inflows (dict): product -> TIME_PERIOD / Net_Flow_kg table of the
          combined (import + domestic) use-phase inflow.
        - import_split (dict): product -> year-indexed pd.Series in [0, 1] with
          the fraction of the total inflow supplied by imports (historical only;
          extend over projected years with build_import_fraction_series).
    """
    total_inflows = {}
    import_split = {}
    for prod in import_inflows:
        imp = import_inflows[prod].set_index("TIME_PERIOD")["Net_Flow_kg"]
        dom = domestic_inflows[prod].set_index("TIME_PERIOD")["Net_Flow_kg"]
        # 1. Align on year and sum (Net_Flow basis, may be negative)
        imp, dom = imp.align(dom, fill_value=0.0)
        total = (imp + dom).rename("Net_Flow_kg")
        # 2. Import split in [0, 1]: positive imports / positive total
        denom = total.where(total > 0)
        split = (
            imp.clip(lower=0.0)
            .div(denom)
            .fillna(0.0)
            .clip(0.0, 1.0)
            .rename("import_share")
        )
        # 3. Package into the expected shapes
        total_df = total.reset_index()
        total_df.columns = ["TIME_PERIOD", "Net_Flow_kg"]
        total_inflows[prod] = total_df
        import_split[prod] = split
    return total_inflows, import_split


def run_old_phase_B(
    eurostat_df,
    product_info,
    lifecycle_stages_names,
    use_phase_stage_number,
    import_inflows,
    build_imp_exp_table,
    translate_to_Ga_MI,
    calculate_flow_driven_MFA,
    calculate_lifecycle_flows,
    build_import_fraction_series,
    combine_lifecycle_flows,
    plot_lifecycle_flows_barplot,
    plot_sankey_lifecycle_flows,
    add_future_BAU_projection,
    raw_import_fraction=1.0,
    product_import_override=None,
    product_growth=0.0,
):
    """Run the superseded combination Phase B (projection + dynamic MFA + lifecycle).

    Builds the domestic use-phase stream from raw-gallium imports, combines it
    with the imported finished-product inflows, projects the combined inflow,
    runs the flow-driven MFA, and propagates it through the lifecycle with the
    two import-fraction scenario knobs. All notebook helpers are passed in so the
    module stays self-contained and importable.

    Args:
        eurostat_df, product_info, lifecycle_stages_names, use_phase_stage_number:
            The notebook's data/config objects.
        import_inflows: Dict product -> TIME_PERIOD / Net_Flow_kg import inflow
            table (the notebook's Phase A step 1 result).
        build_imp_exp_table, translate_to_Ga_MI, calculate_flow_driven_MFA,
        calculate_lifecycle_flows, build_import_fraction_series,
        combine_lifecycle_flows, plot_lifecycle_flows_barplot,
        plot_sankey_lifecycle_flows, add_future_BAU_projection:
            Notebook helper functions.
        raw_import_fraction: Knob 1 (scalar or per-year series). Defaults to 1.0.
        product_import_override: Knob 2 override dict {product: scalar_or_series};
            None uses the computed import split. Defaults to None.
        product_growth: Knob 3 BAU growth rate (scalar or {product: rate}).
            Defaults to 0.0.

    Returns:
        pd.DataFrame: Per-product lifecycle flows (long format).
    """
    # Step 2: domestic use inflow (single, non-product-specific)
    domestic_use_inflow, _ = calculate_domestic_use_inflow(
        eurostat_df,
        RAW_MATERIAL_INFO["raw_Ga"],
        lifecycle_stages_names,
        build_imp_exp_table,
        translate_to_Ga_MI,
        calculate_flow_driven_MFA,
    )
    # Steps 3 + 4: split the domestic inflow by the import-derived split
    split_df = calculate_use_phase_split(import_inflows)
    domestic_inflows = apply_use_phase_split(domestic_use_inflow, split_df)
    # Step 5: combine + import-split time-series
    total_inflows, import_split = combine_use_inflows(import_inflows, domestic_inflows)

    lifecycle_frames = []
    for prod, info in product_info.items():
        # Knob 3: project the combined historical inflow into the future
        growth = (
            product_growth[prod]
            if isinstance(product_growth, dict)
            else product_growth
        )
        inflow_proj = add_future_BAU_projection(total_inflows[prod], growth_rate=growth)

        # Dynamic MFA
        mfa = calculate_flow_driven_MFA(
            inflow_proj,
            show_output=False,
            survival_curve_parameters=info["survival_curve_parameters"],
        )
        years = mfa.index  # historical + projected

        # Knob 1: raw-Ga import fraction -> Manufacturing (time-series aligned)
        lifecycle_stages_names[4]["import_share"] = build_import_fraction_series(
            raw_import_fraction, years
        )
        # Knob 2: product import fraction -> Use (computed split, or override)
        prod_import_fraction = (
            product_import_override[prod]
            if isinstance(product_import_override, dict)
            else import_split[prod]
        )
        lifecycle_stages_names[6]["import_share"] = build_import_fraction_series(
            prod_import_fraction, years
        )

        lf = calculate_lifecycle_flows(
            mfa, lifecycle_stages_names, use_phase_stage_number=use_phase_stage_number
        )
        lf["product"] = prod
        lifecycle_frames.append(lf)

    lifecycle_flows_df = pd.concat(lifecycle_frames, ignore_index=True)

    lifecycle_flows_agg = combine_lifecycle_flows(lifecycle_flows_df)
    plot_lifecycle_flows_barplot(
        lifecycle_flows_agg[lifecycle_flows_agg["year"] == 2021],
        year=2021,
    )
    plot_sankey_lifecycle_flows(
        lifecycle_flows_df,
        year=2021,
        split_stage=use_phase_stage_number,
        plot_waste_per_stage=True,
    )
    return lifecycle_flows_df
