import warnings
from io import BytesIO

import pandas as pd
import plotly.graph_objs as go
import streamlit as st
from plotly import colors
from streamlit_option_menu import option_menu
from waitress.utilities import months
from dateutil.relativedelta import relativedelta

from components import (
    set_header,
    hide_sidebar,
)
from data_utils import (
    calculate_forecasts,
    convert_to_cohort_df,
    record_changes,
)
from db import (
    fetch_experiment,
    fetch_all_experiments,
)
from snowflake_utils import fetch_data_from_db
from data_utils import preprocess

warnings.filterwarnings("ignore")

st.set_page_config(layout="wide", page_title="Forecast Results", initial_sidebar_state="collapsed")
hide_sidebar()
page = option_menu(
    menu_title=None,
    options=["Revenue Upload", "Pipeline Analysis", "Pipeline Forecast", "TopDown Forecast"],
    default_index=2,
    orientation="horizontal",
    icons=["database", "bar-chart-line-fill", "graph-up-arrow", "graph-up-arrow"],
    styles={
        "container": {
            # "background-color": "black",
            # "padding": "10px",
            # "margin": "10px 0px",
            # "font": "sans-serif",
            # "position": "relative",
            "border": "1px solid #d3d3d3",
            "border-radius": "5px",
            "margin": "0px 0px 0px 0px",
            "padding": "0px",
        },
        "nav-link": {
            "font-family": "Verdana, sans-serif",
            "font-size": "0.85rem",
            # "text-align": "left",
            "--hover-color": "grey",
            "--hover-background-color": "white",
            "margin": "0px 0px",
            "border-radius": "0px",
        },
        "nav-link-selected": {"background-color": "red", "color": "white"},
    },
)
if page == 'Pipeline Analysis':
    st.switch_page("pages/1_Analysis.py")
if page == 'TopDown Forecast':
    st.switch_page("pages/3_TopDown.py")
if page == 'Revenue Upload':
    st.switch_page("RevenueUpload.py")
set_header("Forecasting Simulation - Pipeline Forecast")


def fetch_and_forecast_experiment(experiment_name):
    exp_df = convert_to_cohort_df(fetch_experiment("test", experiment_name))
    exp_df['selected'] = exp_df.selected.map({1: True, 0: False})
    cohort_selected_features = list(
        exp_df.drop(["cohort", "eff_probability", "selected"], axis=1).columns
    )

    st.session_state["cohort_information"][experiment_name] = {}
    st.session_state["cohort_information"][experiment_name][
        "cohort_df"
    ] = exp_df.copy()
    st.session_state["cohort_information"][experiment_name][
        "cohort_selected_features"
    ] = cohort_selected_features.copy()

    # st.write(st.session_state["cohort_df"])
    _df = st.session_state["future_df"].copy()
    _df[cohort_selected_features] = _df[cohort_selected_features].fillna(
        "None"
    )

    _df = _df.merge(exp_df, on=cohort_selected_features, how="left").copy()

    _df["final_probability"] = _df["eff_probability"].fillna(0)
    temp = _df.copy()

    if not exp_df.iloc[0]['selected']:
        ids = temp[
            temp['deal_probability'] != temp['effective_probability']
            ].index
        temp.loc[ids, 'final_probability'] = temp.loc[
            ids, 'effective_probability']

        temp.loc[ids, 'cohort'] = 'cohort 0'

    _df = temp.copy()
    forecast_results = calculate_forecasts(
        _df, ["final_probability"], ["amount"], st.session_state["actual_max_date_str"]
    )

    st.session_state["forecast_resultss"][
        experiment_name
    ] = forecast_results.copy()
    return exp_df, cohort_selected_features, _df


with open("./styles.css") as f:
    st.markdown(
        f"<style>{f.read()}</style>",
        unsafe_allow_html=True,
    )
if "all_experiments" not in st.session_state:
    # st.error("Please run the Analysis page first")
    # st.stop
    st.session_state["all_experiments"] = fetch_all_experiments("test")

if "cohort_information" not in st.session_state:
    st.session_state["cohort_information"] = {}

if "forecast_resultss" not in st.session_state:
    st.session_state["forecast_resultss"] = {}

if "future_df" not in st.session_state:
    data = fetch_data_from_db(f"'{st.session_state['actual_max_date_str']}'")
    _, st.session_state["future_df"] = preprocess(data)

left_pane, main_pane = st.columns((0.25, 0.75))

with left_pane:
    if 'reporting-experiments-p2' not in st.session_state:
        st.session_state['reporting-experiments-p2'] = ["Existing Approach", "Default"]
    st.multiselect(
        "Select Experiments for Comparison",
        options=["Existing Approach", "Default"]
                + st.session_state["all_experiments"],
        key="reporting-experimentss-p2",
        default=st.session_state['reporting-experiments-p2'],
        on_change=record_changes,
        args=("reporting-experiments-p2", "reporting-experimentss-p2"),
        help='Existing Approach: Maximum of Deal and Effective probability\n\nDefault: Deal probability',
    )

    experiments = st.session_state["reporting-experiments-p2"]
    experiments = [e for e in experiments if e not in ["Existing Approach", "Default"]]
    if len(experiments) > 0:
        for experiment in experiments:
            _T = fetch_and_forecast_experiment(experiment)

    if "period" not in st.session_state:
        st.session_state["period"] = "6 Months"
    st.selectbox(
        "Select Period",
        options=["Quarter", "6 Months", "1 Year"],
        key="periodd",
        index=(["Quarter", "6 Months", "1 Year"]).index(st.session_state['period']),
        on_change=record_changes,
        args=("period", "periodd"),
    )
    st.session_state['period_to_date'] = {"Quarter": (pd.to_datetime(st.session_state['actual_max_date_str']) + relativedelta(months=+3)).strftime('%Y-%m-%d'),
                                            "6 Months": (pd.to_datetime(st.session_state['actual_max_date_str']) + relativedelta(months=+6)).strftime('%Y-%m-%d'),
                                          "1 Year": (pd.to_datetime(st.session_state['actual_max_date_str']) + relativedelta(years=+1)).strftime('%Y-%m-%d')}

    if 'selected_report_experiment' not in st.session_state:
        st.session_state['selected_report_experiment'] = None
    st.selectbox(
        "Select Experiment for report",
        options=['Current', 'Existing Approach', 'Default'] + st.session_state["all_experiments"],
        key='selected_report_experimentt',
        index=(['Current', 'Existing Approach', 'Default'] + st.session_state["all_experiments"]).index(
            st.session_state['selected_report_experiment']) if st.session_state['selected_report_experiment'] in [
            'Current', 'Existing Approach', 'Default'] + st.session_state["all_experiments"] else None,
        on_change=record_changes,
        args=("selected_report_experiment", "selected_report_experimentt"),
    )
    if st.session_state['selected_report_experiment']:
        if st.session_state['selected_report_experiment'] not in ['Current', 'Existing Approach', 'Default']:
            _F = fetch_and_forecast_experiment(st.session_state['selected_report_experiment'])

    # st.text_input('Enter Excel file name (e.g. email_data.xlsx)', key='filename')

with main_pane:
    with st.expander("Future Forecasts"):
        if "sl_df" not in st.session_state:
            st.session_state["sl_df"] = pd.read_csv("sl_proportions.csv")
            st.session_state["sl_df"] = st.session_state["sl_df"][
                ~st.session_state["sl_df"].ASSOCIATED_DEAL_IDS.isna()].copy()
            st.session_state["sl_df"]["ASSOCIATED_DEAL_IDS"] = st.session_state["sl_df"][
                "ASSOCIATED_DEAL_IDS"].apply(lambda x: str(x).replace(".0", ""))
            st.session_state["sl_list"] = sorted(st.session_state["sl_df"].NAME.unique())

        st.selectbox("Service line", options=["Overall"] + st.session_state["sl_list"], key="sl_selected", index=0)

        st.session_state["future_df_"] = st.session_state["future_df"].copy()
        _exp_columns = []

        for experiment_name in ["Current"] + st.session_state["reporting-experiments-p2"]:
            if "cohort_information" in st.session_state:
                cohort_info = st.session_state["cohort_information"].get(experiment_name, {})
                if cohort_info:
                    cohort_df = cohort_info["cohort_df"]
                    cohort_selected_features = cohort_info["cohort_selected_features"]
                    st.session_state["future_df_"][cohort_selected_features] = st.session_state["future_df_"][
                        cohort_selected_features].fillna("None")
                    st.session_state["future_df_"] = st.session_state["future_df_"].merge(
                        cohort_df[cohort_selected_features + ["eff_probability"]],
                        on=cohort_selected_features,
                        how="left"
                    ).rename(columns={"eff_probability": f"{experiment_name}_prob"})

                    if not cohort_df.iloc[0]["selected"]:
                        ids = st.session_state["future_df_"][
                            st.session_state["future_df_"]['deal_probability'] != st.session_state["future_df_"][
                                'effective_probability']].index
                        st.session_state["future_df_"].loc[ids, f"{experiment_name}_prob"] = \
                            st.session_state["future_df_"].loc[ids, 'effective_probability']

                    _exp_columns.append(experiment_name)

                if experiment_name == "Current":
                    if "forecast_results" not in st.session_state:
                        continue
                    if len(st.session_state["forecast_results"].get("Current", {})) == 0:
                        if experiment_name in _exp_columns:
                            _exp_columns.remove(experiment_name)
                        continue

        forecast_results = calculate_forecasts(
            st.session_state["future_df_"],
            [
                "final_probability",
                "deal_probability",
                *[f"{e}_prob" for e in _exp_columns],
            ],
            [
                "amount_Existing Approach",
                "amount_Default",
                *[f"amount_{e}" for e in _exp_columns],
            ],
            st.session_state['period_to_date'][st.session_state['period']],
            rename=False,
        )

        res = pd.concat([list(d.values())[0].set_index(["record_id", "date"]) for d in forecast_results],
                        axis=1).reset_index()
        res.date = res.date.dt.date
        res = res.merge(st.session_state["sl_df"], left_on="record_id", right_on="ASSOCIATED_DEAL_IDS", how="left")
        amount_columns = [c for c in res.columns if c.startswith("amount")]
        for col in amount_columns:
            res[col] = res[col] * res["PROP"]
        if st.session_state["sl_selected"] != "Overall":
            res = res[res["NAME"] == st.session_state["sl_selected"]]
        res = res.groupby("date")[amount_columns].sum().reset_index()

        fig = go.Figure()

        for i, experiment_name in enumerate(["Current"] + st.session_state["reporting-experiments-p2"]):
            if experiment_name == "Current":
                if "forecast_results" not in st.session_state:
                    continue
                if len(st.session_state["forecast_results"].get("Current", {})) == 0:
                    continue
            fig.add_trace(
                go.Scatter(
                    x=res["date"],
                    y=res[f"amount_{experiment_name}"],
                    mode="lines",
                    name=experiment_name,
                    line={
                        "color": colors.DEFAULT_PLOTLY_COLORS[i + 1 % 10]
                    },
                )
            )

        # Customize layout
        fig.update_layout(
            title="Future Prediction",
            xaxis_title="Date",
            yaxis_title="Amount (in $)",
            # legend_title_text='Features'
        )

        # Show the plot
        st.plotly_chart(fig)

        st.table(
            res.rename(
                columns={
                    "amount": "Existing",
                    "date": "Date",
                    **{
                        f"amount_{e}": e
                        for e in st.session_state["reporting-experiments-p2"]
                    },
                }
            )
            .style.set_table_styles(
                [
                    {
                        "selector": "thead  th",
                        "props": "background-color: #2d7dce; text-align:center; color: white;font-size:0.9rem;border-bottom: 1px solid black !important;",
                    },
                    {
                        "selector": "tbody  th",
                        "props": "font-weight:bold;font-size:0.9rem;color:#000;",
                    },
                    {
                        "selector": "tbody  tr:nth-child(2n + 2)",
                        "props": "background-color: #aacbec;",
                    },
                ],
                overwrite=False,
            )
            .format(precision=0, thousands=",")
        )

    with st.expander("Future Report"):
        st.session_state["future_df_"] = st.session_state["future_df"].copy()
        experiment_name = st.session_state['selected_report_experiment']
        _exp_columns = []

        if "cohort_information" in st.session_state:
            if experiment_name in st.session_state["cohort_information"]:
                cohort_info = st.session_state["cohort_information"][experiment_name]
                cohort_df = cohort_info["cohort_df"]
                cohort_selected_features = cohort_info["cohort_selected_features"]

                st.session_state["future_df_"][cohort_selected_features] = st.session_state["future_df_"][
                    cohort_selected_features].fillna("None")
                st.session_state["future_df_"] = st.session_state["future_df_"].merge(
                    cohort_df[cohort_selected_features + ["eff_probability"]],
                    on=cohort_selected_features,
                    how="left"
                ).rename(columns={"eff_probability": f"{experiment_name}_prob"})

                if not cohort_df.iloc[0]["selected"]:
                    ids = st.session_state["future_df_"][
                        st.session_state["future_df_"]['deal_probability'] != st.session_state["future_df_"][
                            'effective_probability']].index
                    st.session_state["future_df_"].loc[ids, f"{experiment_name}_prob"] = \
                        st.session_state["future_df_"].loc[ids, 'effective_probability']

                _exp_columns.append(experiment_name)

        forecast_results = calculate_forecasts(
            st.session_state["future_df_"],
            ["final_probability", "deal_probability"] + [f"{e}_prob" for e in _exp_columns],
            ["amount_Existing Approach", "amount_Default"] + [f"amount_{e}" for e in _exp_columns],
            st.session_state['period_to_date'][st.session_state['period']],
            rename=False
        )

        res = pd.concat([list(d.values())[0].set_index(["record_id", "date"]) for d in forecast_results],
                        axis=1).reset_index()
        res.date = res.date.dt.date
        res = res.merge(st.session_state["sl_df"], left_on="record_id", right_on="ASSOCIATED_DEAL_IDS", how="left")
        amount_columns = [c for c in res.columns if c.startswith("amount")]
        for col in amount_columns:
            res[col] = res[col] * res["PROP"]

        res_ = res.merge(
            st.session_state['future_df_'][
                ['record_id', 'customer_segment', 'associated_company', 'deal_name', 'deal_stage', 'pipeline']],
            on='record_id',
            how='left'
        ).fillna('Unassigned')

        map_deal_pipeline = {
            '0_new': 'Pipeline 0-2', '1_connected_to_meet': 'Pipeline 0-2', '2_needs_expressed': 'Pipeline 0-2',
            '3_qualified_oppurtunity': 'Pipeline 3-6', '4_proposal_presented': 'Pipeline 3-6',
            '5_verbal_agreement': 'Pipeline 3-6',
            '6_contracting': 'Pipeline 3-6', '7_closed_won': '7_closed_lost', '7_closed_lost': 'Backlog'
        }
        res_['Category'] = res_['deal_stage'].map(map_deal_pipeline)
        st.session_state['res_'] = res_.copy()
        if (experiment_name in ['Existing Approach', 'Default']) or (
                "cohort_information" in st.session_state and experiment_name in st.session_state["cohort_information"]):
            pivot_res = res_.pivot_table(
                index=['Category', 'pipeline', 'associated_company', 'record_id', 'deal_name', 'deal_stage',
                       'customer_segment',
                       'NAME'],
                columns='date',
                values=f'amount_{experiment_name}',
                aggfunc='sum'
            ).reset_index().fillna(0)

            pivot_res.columns = [
                pd.to_datetime(col, errors='coerce') if col not in ['Category', 'pipeline', 'associated_company',
                                                                    'record_id',
                                                                    'deal_name',
                                                                    'deal_stage', 'customer_segment',
                                                                    'NAME', ]
                else col for col in pivot_res.columns]
            date_columns = [col for col in pivot_res.columns if isinstance(col, pd.Timestamp)]
            years = sorted(set(col.year for col in date_columns))

            cumulative_sum_df = pivot_res.copy()
            for year in years:
                year_columns = [col for col in date_columns if col.year == year]
                cumulative_sum_df[f'Cumulative_{year}'] = pivot_res[year_columns].sum(axis=1)
            updated_date_columns = [col.strftime('%b-%y') for col in date_columns]
            cumulative_sum_df.rename(columns={old: new for old, new in zip(date_columns, updated_date_columns)},
                                     inplace=True)
            st.session_state['final_all_sum_df'] = cumulative_sum_df.copy()

            client_view = cumulative_sum_df.drop(columns=['pipeline'])
            client_view = client_view.rename(columns={
                'associated_company': 'COMPANY', 'record_id': 'HUBSPOT_ID', 'deal_name': "DEAL",
                'deal_stage': 'STAGE', 'customer_segment': "SEGMENT", 'NAME': 'SERVICE'
            })

            st.markdown(f"<div class='selected-snapshot'>Selected Experiment for Report : {experiment_name}</div>",
                        unsafe_allow_html=True)
            filename = f"{experiment_name}_forecast_report"
            if filename:
                if not filename.endswith(".xlsx"):
                    filename += ".xlsx"
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    client_view.to_excel(writer, index=False, sheet_name='All Service Lines')
                    final_all_sum_df = st.session_state['final_all_sum_df'].copy()
                    depts = final_all_sum_df['NAME'].unique()
                    for dept in depts:
                        dept_df = final_all_sum_df[final_all_sum_df['NAME'] == dept]
                        dept_df.to_excel(writer, sheet_name=dept, index=False)
                    writer.close()
                st.download_button(label="Download Report", data=buffer.getvalue(), file_name=filename,
                                   mime="application/vnd.ms-excel", key='download_report')
            st.table(
                client_view.style.set_table_styles
                    (
                    [
                        {
                            "selector": "thead  th",
                            "props": "background-color: #2d7dce; text-align:center; color: white;font-size:0.9rem;border-bottom: 1px solid black !important;",
                        },
                        {
                            "selector": "tbody  th",
                            "props": "font-weight:bold;font-size:0.9rem;color:#000;",
                        },
                    ],
                    overwrite=False,
                )
                .format(precision=0, thousands=",")
            )

    # st.write(st.session_state)
    # if "sl_df" not in st.session_state:
    #     st.session_state["sl_df"] = pd.read_csv("sl_proportions.csv")
    #     st.session_state["sl_df"] = st.session_state["sl_df"][
    #         ~st.session_state["sl_df"].ASSOCIATED_DEAL_IDS.isna()
    #     ].copy()
    #     st.session_state["sl_df"][
    #         "ASSOCIATED_DEAL_IDS"
    #     ] = st.session_state["sl_df"]["ASSOCIATED_DEAL_IDS"].apply(
    #         lambda x: str(x).replace(".0", "")
    #     )
    #     st.session_state["sl_list"] = sorted(
    #         list(st.session_state["sl_df"].NAME.unique())
    #     )
    #
    # st.selectbox(
    #     "Service line",
    #     options=["Overall"] + st.session_state["sl_list"],
    #     key="sl_selected",
    #     index=0,
    # )
    #
    # st.session_state["future_df_"] = st.session_state["future_df"]
    # st.write(st.session_state["cohort_information"])
    # st.write(st.session_state["future_df_"])
    # _exp_columns = []
    # for experiment_name in ["Current"] + st.session_state["reporting-experiments-p2"]:
    #     if len(st.session_state["cohort_information"].get(experiment_name, {})) > 0:
    #         st.write("Experiment Name", experiment_name)
    #         cohort_df = st.session_state["cohort_information"][experiment_name]["cohort_df"]
    #         cohort_selected_features = st.session_state["cohort_information"][experiment_name][
    #             "cohort_selected_features"]
    #         st.session_state["future_df_"][cohort_selected_features] = st.session_state["future_df"][
    #             cohort_selected_features
    #         ].fillna(
    #             "None"
    #         )
    #         # st.write("Cohort df", cohort_df)
    #         # st.write("Before merge", st.session_state["future_df_"])
    #         st.session_state["future_df_"] = (
    #             st.session_state["future_df_"]
    #             .merge(
    #                 cohort_df[
    #                     [*cohort_selected_features, "eff_probability"]
    #                 ],
    #                 on=cohort_selected_features,
    #                 how="left",
    #             )
    #             .rename(
    #                 columns={
    #                     "eff_probability": f"{experiment_name}_prob"
    #                 }
    #             )
    #             .copy()
    #         )
    #         temp = st.session_state['future_df_'].copy()
    #
    #         if cohort_df.iloc[0]['selected'] == False:
    #             ids = temp[
    #                 temp['deal_probability'] != temp['effective_probability']
    #                 ].index
    #             temp.loc[ids, f"{experiment_name}_prob"] = temp.loc[
    #                 ids, 'effective_probability']
    #         st.session_state["future_df_"] = temp.copy()
    #         # st.write("After merge", st.session_state["future_df_"])
    #         _exp_columns.append(experiment_name)
    #
    #     if experiment_name == "Current":
    #         if len(st.session_state["forecast_results"].get("Current", {})) == 0:
    #             if experiment_name in _exp_columns:
    #                 _exp_columns.remove(experiment_name)
    #             continue
    #
    # forecast_results = calculate_forecasts(
    #     st.session_state["future_df_"],
    #     [
    #         "final_probability",
    #         "deal_probability",
    #         *[f"{e}_prob" for e in _exp_columns],
    #     ],
    #     [
    #         "amount_Existing Approach",
    #         "amount_Default",
    #         *[f"amount_{e}" for e in _exp_columns],
    #     ],
    #     st.session_state["period_to_date"][st.session_state["period"]],
    #     rename=False,
    # )
    #
    # res = pd.concat(
    #     [
    #         list(d.values())[0].set_index(["record_id", "date"])
    #         for d in forecast_results
    #     ],
    #     axis=1,
    # ).reset_index()
    # res.date = res.date.dt.date
    # res = res.merge(
    #     st.session_state["sl_df"],
    #     left_on="record_id",
    #     right_on="ASSOCIATED_DEAL_IDS",
    #     how="left",
    # )
    # amount_columns = [c for c in res.columns if c.startswith("amount")]
    # for col in amount_columns:
    #     res[col] = res[col] * res["PROP"]
    # if st.session_state["sl_selected"] != "Overall":
    #     res = res[res["NAME"] == st.session_state["sl_selected"]]
    #
    # # res_ = res.copy()
    # # pivot_res = res_.pivot_table(index=['record_id', 'NAME'], columns='date', values='amount_Current',
    # #                              aggfunc='sum').reset_index().fillna(0)
    # #
    # # pivot_res.columns = [pd.to_datetime(col, errors='coerce') if col not in ['record_id', 'NAME'] else col for
    # #                      col in pivot_res.columns]
    # # date_columns = [col for col in pivot_res.columns if isinstance(col, pd.Timestamp)]
    # # years = sorted(set(col.year for col in date_columns))
    # #
    # # cumulative_sum_df = pivot_res.copy()
    # # for year in years:
    # #     year_columns = [col for col in date_columns if col.year == year]
    # #     cumulative_sum = pivot_res[year_columns].sum(axis=1)
    # #     cumulative_sum_df[f'Cumulative_{year}'] = cumulative_sum
    # res = res.groupby("date")[amount_columns].sum().reset_index()
    #
    # fig = go.Figure()
    #
    # for i, experiment_name in enumerate(
    #         ["Current"] + st.session_state["reporting-experiments-p2"]
    # ):
    #     if experiment_name == "Current":
    #         if (
    #                 len(
    #                     st.session_state["forecast_results"].get(
    #                         "Current", {}
    #                     )
    #                 )
    #                 == 0
    #         ):
    #             continue
    #     fig.add_trace(
    #         go.Scatter(
    #             x=res["date"],
    #             y=res[f"amount_{experiment_name}"],
    #             mode="lines",
    #             name=experiment_name,
    #             line={
    #                 "color": colors.DEFAULT_PLOTLY_COLORS[i + 1 % 10]
    #             },
    #         )
    #     )
    #
    # # Customize layout
    # fig.update_layout(
    #     title="Future Prediction",
    #     xaxis_title="Date",
    #     yaxis_title="Amount (in $)",
    #     # legend_title_text='Features'
    # )
    #
    # # Show the plot
    # st.plotly_chart(fig)
    # with st.expander("Future Results"):
    #     st.table(
    #         res.rename(
    #             columns={
    #                 "amount": "Existing",
    #                 "date": "Date",
    #                 **{
    #                     f"amount_{e}": e
    #                     for e in st.session_state["reporting-experiments-p2"]
    #                 },
    #             }
    #         )
    #         .style.set_table_styles(
    #             [
    #                 {
    #                     "selector": "thead  th",
    #                     "props": "background-color: #2d7dce; text-align:center; color: white;font-size:0.9rem;border-bottom: 1px solid black !important;",
    #                 },
    #                 {
    #                     "selector": "tbody  th",
    #                     "props": "font-weight:bold;font-size:0.9rem;color:#000;",
    #                 },
    #                 {
    #                     "selector": "tbody  tr:nth-child(2n + 2)",
    #                     "props": "background-color: #aacbec;",
    #                 },
    #             ],
    #             overwrite=False,
    #         )
    #         .format(precision=0, thousands=",")
    #     )
    # # with st.expander("Report"):
    # #     st.table(
    # #         # cumulative_sum_df.rename(
    # #         #     columns={
    # #         #         "amount": "Existing",
    # #         #         "date": "Date",
    # #         #         **{
    # #         #             f"amount_{e}": e
    # #         #             for e in st.session_state["reporting-experiments-p2"]
    # #         #         },
    # #         #     }
    # #         # )
    # #     cumulative_sum_df
    # #         .style.set_table_styles(
    # #             [
    # #                 {
    # #                     "selector": "thead  th",
    # #                     "props": "background-color: #2d7dce; text-align:center; color: white;font-size:0.9rem;border-bottom: 1px solid black !important;",
    # #                 },
    # #                 {
    # #                     "selector": "tbody  th",
    # #                     "props": "font-weight:bold;font-size:0.9rem;color:#000;",
    # #                 },
    # #                 {
    # #                     "selector": "tbody  tr:nth-child(2n + 2)",
    # #                     "props": "background-color: #aacbec;",
    # #                 },
    # #             ],
    # #             overwrite=False,
    # #         )
    # #         .format(precision=0, thousands=",")
    # #     )
    # st.write(st.session_state)