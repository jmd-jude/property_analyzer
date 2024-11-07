import streamlit as st
import re
from api.rentcast import RentcastAPI
from api.openai_service import OpenAIService
from scoring.property_scorer import PropertyScorer

# Initialize services
scorer = PropertyScorer()

def get_zip_from_address(address: str) -> str:
    """Extract zip code from address string"""
    zip_match = re.search(r'\b\d{5}\b', address)
    return zip_match.group(0) if zip_match else None

def display_score_results(result: dict):
    """Display scoring results in a structured way"""
    # Create tabs for different sections of the analysis
    overview_tab, details_tab, analysis_tab = st.tabs(["Overview", "Detailed Metrics", "Analysis"])
    
    with overview_tab:
        # Overall Score Card
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Score", f"{result['total_score']}/100")
        with col2:
            st.metric("Confidence Level", result['confidence'].upper())
            
        # Value Analysis Summary
        if 'value_analysis' in result:
            value = result['value_analysis']
            st.subheader("Value Analysis")
            cols = st.columns(2)
            with cols[0]:
                st.metric("Estimated Value", f"${value.get('estimated_value', 0):,.2f}")
            with cols[1]:
                st.metric("Value Range", 
                    f"${value.get('value_range_low', 0):,.0f} - ${value.get('value_range_high', 0):,.0f}")
            
        # Key Factors Summary
        st.subheader("Key Highlights")
        for factor in result['factors'][:3]:  # Show top 3 factors
            st.write(f"• {factor}")
            
    with details_tab:
        # Score Breakdown
        st.subheader("Score Breakdown")
        cols = st.columns(3)
        with cols[0]:
            st.metric("Value Score", result['value_score'])
        with cols[1]:
            st.metric("Location Score", result['location_score'])
        with cols[2]:
            st.metric("Feature Score", result.get('feature_score', 0))

        # Market Context
        if result.get('market_context'):
            st.subheader("Market Context")
            market = result['market_context']
            metrics_cols = st.columns(2)
            with metrics_cols[0]:
                st.metric("Average Value", f"${market.get('avg_value', 0):,.2f}")
                st.metric("Properties Analyzed", market.get('total_properties', 0))
            with metrics_cols[1]:
                st.metric("Avg Price/SqFt", f"${market.get('avg_price_sqft', 0):,.2f}")
                st.metric("Avg Days on Market", f"{market.get('avg_days_on_market', 0):.0f}")

        # Comparable Properties
        if result.get('validation_examples'):
            st.subheader("Comparable Properties")
            for example in result['validation_examples']:
                with st.expander(f"Property: {example['formattedAddress']}"):
                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("Square Footage", f"{example['squareFootage']:,}")
                        st.metric("Bedrooms", example['bedrooms'])
                    with cols[1]:
                        st.metric("Price", f"${example.get('price', 0):,.2f}")
                        st.metric("Bathrooms", example['bathrooms'])
                    with cols[2]:
                        st.metric("Days on Market", example.get('daysOnMarket', 'N/A'))
                        if 'correlation' in example:
                            st.metric("Similarity", f"{example['correlation']*100:.1f}%")

    with analysis_tab:
        # AI Analysis
        if result.get('ai_analysis'):
            # Add custom CSS to improve markdown formatting
            st.markdown("""
                <style>
                    .stMarkdown h1 {
                        color: #1F618D;
                        font-size: 1.8em;
                        margin-top: 1.5em;
                        margin-bottom: 0.8em;
                        padding-bottom: 0.3em;
                        border-bottom: 1px solid #eaecef;
                    }
                    
                    .stMarkdown h2 {
                        color: #2874A6;
                        font-size: 1.5em;
                        margin-top: 1.2em;
                        margin-bottom: 0.5em;
                    }
                    
                    .stMarkdown ul {
                        margin-bottom: 1em;
                        margin-left: 1.5em;
                    }
                    
                    .stMarkdown li {
                        margin-bottom: 0.3em;
                        line-height: 1.6;
                    }
                    
                    .stMarkdown p {
                        margin-bottom: 1em;
                        line-height: 1.8;
                    }
                    
                    .stMarkdown strong {
                        color: #2C3E50;
                    }
                </style>
                """, unsafe_allow_html=True)
            
            # Create a container with padding
            with st.container():
                st.markdown(result['ai_analysis'])
        else:
            st.warning("AI analysis is currently unavailable.")

def main():
    st.set_page_config(
        page_title="Property Investment Analysis",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("Property Investment Analysis")
    st.markdown("""
    Enter a property address and your considered purchase price to get a comprehensive investment analysis.
    """)
    
    with st.form(key='property_form'):
        address = st.text_input(
            "Enter the property address (including zip code)",
            help="Example: 123 Main Street, San Antonio, TX 78244"
        )
        price_considered = st.number_input(
            "Enter the price you are considering ($)", 
            min_value=0, 
            step=1000,
            help="Enter the price you're considering offering for this property"
        )
        submit_button = st.form_submit_button("Analyze Property")
    
    if submit_button and address and price_considered:
        with st.spinner('Analyzing property...'):
            try:
                # Get zip code from address
                zip_code = get_zip_from_address(address)
                if not zip_code:
                    st.error("Please include a valid zip code in the address.")
                    return

                # Get property score and analysis
                result = scorer.score_property(address, price_considered)
                
                if result['total_score'] > 0:
                    display_score_results(result)
                else:
                    st.error("Unable to analyze this property. Please check the address and try again.")
                    
            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")
                st.error("Please try again or contact support if the problem persists.")

if __name__ == "__main__":
    main()