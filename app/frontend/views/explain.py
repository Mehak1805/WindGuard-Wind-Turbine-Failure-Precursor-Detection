"""Page 4 - Explainability: top drivers per flag, sensor importance, model comparison."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

ui.setup("Explainability")
ui.hero("Explainability", "Why was this turbine flagged? Pick an alert to see the sensors that moved, then compare the models behind the score.")

st.markdown("#### Why was this alert raised?")
al = api.get("/alerts", limit=60)
if not al:
    st.info("No alerts yet - let the replay run or press **Next alert** in the sidebar.")
else:
    labels = {a["alert_id"]: f"Turbine {a['turbine_id']} · {pd.Timestamp(a['start']).strftime('%b %d %H:%M')} · {a['band']} · {a['status']}" for a in al}
    pick = st.selectbox("Alert", list(labels), format_func=labels.get)
    ex = api.get(f"/explain/alert/{pick}")
    c1, c2, c3 = st.columns([1.3, 1.3, 1])
    with c1.container(border=True):
        st.markdown("**Top drivers at the peak** (from the risk model)")
        d = pd.DataFrame(ex["drivers"])
        if len(d):
            ch = alt.Chart(d).mark_bar().encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)), x=alt.X("sigma:Q", title="deviation from normal (σ)"),
                                                color=alt.condition(alt.datum.sigma > 0, alt.value("#2a78d6"), alt.value("#d03b3b")), tooltip=["sensor", "sigma"])
            ui.show(ch, 210)
        st.caption(f"Peak {pd.Timestamp(ex['peak_ts']).strftime('%b %d %H:%M')} · risk {ui.pct(ex['peak_risk'], 0)} · regime {ex['regime']}")
    with c2.container(border=True):
        st.markdown("**Condition sensors vs. healthy behaviour** (robust z-score)")
        z = pd.DataFrame(ex["sensor_deviation"]); z["sensor"] = z["sensor"].str.replace(r" \(.*\)", "", regex=True)
        ch = alt.Chart(z).mark_bar().encode(y=alt.Y("sensor:N", sort=None, title=None), x=alt.X("z:Q", title="z-score"),
                                            color=alt.condition(alt.datum.z > 0, alt.value("#2a78d6"), alt.value("#d03b3b")), tooltip=["sensor", "z"])
        ui.show(ch, 210)
    with c3.container(border=True):
        st.markdown("**Do the models agree?**")
        mp = pd.DataFrame(dict(model=list(ex["model_probs"]), p=list(ex["model_probs"].values())))
        ch = alt.Chart(mp).mark_bar(color=ui.BRAND, cornerRadiusEnd=3).encode(y=alt.Y("model:N", sort=None, title=None), x=alt.X("p:Q", title=None, scale=alt.Scale(domain=[0, 1])), tooltip=["model", alt.Tooltip("p:Q", format=".2f")])
        ui.show(ch, 210)

g = api.get("/explain/global")
st.markdown("#### Which sensors matter most?")
l, r = st.columns([3, 2])
with l:
    imp = pd.DataFrame(g["importance"]).sort_values("perm_drop_pr_auc", ascending=False)
    imp["sensor"] = imp["sensor_group"].str.replace(r" \(.*\)", "", regex=True)
    ch = alt.Chart(imp).mark_bar(color=ui.BRAND, cornerRadiusEnd=3).encode(y=alt.Y("sensor:N", sort=None, title=None), x=alt.X("perm_drop_pr_auc:Q", title="drop in PR-AUC when the sensor is scrambled"),
                                                                           tooltip=["sensor", alt.Tooltip("perm_drop_pr_auc:Q", format=".3f"), alt.Tooltip("rf_gini_share:Q", format=".3f")])
    ui.show(ch, 400)
with r:
    st.markdown("**Fusion weights** (how the final risk blends its parts)")
    fw = pd.DataFrame(g["fusion"])
    ch = alt.Chart(fw).mark_bar(color=ui.BRAND_DARK, cornerRadiusEnd=3).encode(y=alt.Y("component:N", sort="-x", title=None, axis=alt.Axis(labelLimit=230)), x=alt.X("weight:Q", title="stacker weight"))
    ui.show(ch, 230)
    st.caption("Permutation importance is grouped by sensor: all features made from one sensor are scrambled together.")

st.markdown("#### Model comparison (test year)")
m = pd.DataFrame(g["models"])
keep = ["model", "family", "pr_auc", "roc_auc", "precision", "recall", "f1", "episode_recall", "median_lead_days", "fa_per_turbine_year"]
st.dataframe(m[[c for c in keep if c in m.columns]].rename(columns={"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "episode_recall": "Failures caught", "median_lead_days": "Lead (d)", "fa_per_turbine_year": "False alarms / turbine-yr"}),
             hide_index=True, width="stretch",
             column_config={"PR-AUC": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"), "ROC-AUC": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                            "precision": st.column_config.NumberColumn(format="%.2f"), "recall": st.column_config.NumberColumn(format="%.2f"), "f1": st.column_config.NumberColumn(format="%.2f"),
                            "Failures caught": st.column_config.NumberColumn(format="%.2f"), "Lead (d)": st.column_config.NumberColumn(format="%.1f"), "False alarms / turbine-yr": st.column_config.NumberColumn(format="%.0f")})
st.caption("Thresholds are chosen on 2021 and applied unchanged to 2022. The reference rule and the raw-level ablation show what the residual features add.")
