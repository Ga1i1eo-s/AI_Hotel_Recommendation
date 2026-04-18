from __future__ import annotations

import streamlit as st

from src.phase2.schemas import PreferenceValidationRequest
from src.phase2.service import get_supported_cuisines, get_supported_locations, validate_preferences
from src.phase3.service import generate_candidate_shortlist
from src.phase4.service import generate_recommendations


@st.cache_data(show_spinner=False)
def load_locations() -> list[str]:
    return get_supported_locations()


@st.cache_data(show_spinner=False)
def load_cuisines() -> list[str]:
    return get_supported_cuisines()


def render_recommendation_cards(recommendations: list[dict]) -> None:
    if not recommendations:
        st.info("No recommendations found for the selected filters.")
        return

    for item in recommendations:
        candidate = item.get("candidate", {})
        with st.container(border=True):
            title = f"{item.get('rank', '-')}. {candidate.get('name', 'Unknown')}"
            st.subheader(title)
            st.caption(
                f"{candidate.get('city', 'N/A')}, {candidate.get('area', 'N/A')} | "
                f"Rating: {candidate.get('rating', 'N/A')} | "
                f"Cost for two: {candidate.get('avg_cost_for_two', 'N/A')}"
            )
            st.write(item.get("reason", "No reason returned."))
            match_tags = item.get("match_tags") or []
            if match_tags:
                st.write("Tags:", ", ".join(match_tags))


def main() -> None:
    st.set_page_config(page_title="Culinary AI Backend", page_icon=":fork_and_knife:", layout="wide")
    st.title("Culinary AI - Backend Console (Streamlit)")
    st.caption("Deploy this app on Streamlit Cloud to host backend recommendation workflow.")

    try:
        locations = load_locations()
    except FileNotFoundError as error:
        st.error(str(error))
        st.stop()

    try:
        cuisines = load_cuisines()
    except FileNotFoundError as error:
        st.error(str(error))
        st.stop()

    with st.form("recommendation_form"):
        col1, col2 = st.columns(2)
        with col1:
            location = st.selectbox("Location", options=locations, index=0 if locations else None)
            cuisine = st.selectbox("Cuisine", options=cuisines, index=0 if cuisines else None)
        with col2:
            budget = st.slider("Budget (max cost for two)", min_value=100, max_value=5000, value=1800, step=50)
            min_rating = st.slider("Minimum rating", min_value=0.0, max_value=5.0, value=4.0, step=0.1)
        additional_preferences = st.text_input("Additional preferences", value="family friendly")
        top_k = st.slider("Top recommendations (k)", min_value=1, max_value=20, value=5)

        submitted = st.form_submit_button("Get AI Recommendations")

    if not submitted:
        return

    request = PreferenceValidationRequest(
        location=location,
        budget=float(budget),
        cuisine=[cuisine] if cuisine else [],
        min_rating=float(min_rating),
        additional_preferences=additional_preferences,
    )

    with st.spinner("Generating recommendations..."):
        validation_response = validate_preferences(request)
        shortlist_response = generate_candidate_shortlist(request)
        recommendation_response = generate_recommendations(request=request, top_k=top_k)

    if validation_response.warnings:
        st.warning(" | ".join(validation_response.warnings))

    if shortlist_response.relaxation_steps_applied:
        st.info("Relaxation steps: " + " -> ".join(shortlist_response.relaxation_steps_applied))

    st.success(
        "Generated recommendations using "
        + ("LLM ranking." if recommendation_response.llm_used else "deterministic fallback.")
    )

    response_payload = recommendation_response.model_dump()
    render_recommendation_cards(response_payload.get("recommendations", []))

    with st.expander("Debug payload"):
        st.json(response_payload)


if __name__ == "__main__":
    main()
