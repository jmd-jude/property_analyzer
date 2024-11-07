import logging
from typing import Dict
from openai import OpenAI
import streamlit as st

class OpenAIService:
    def __init__(self):
        """Initialize OpenAI service with API key from Streamlit secrets"""
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def generate_property_analysis(self, scoring_data: Dict) -> str:
        """Generate detailed property analysis using OpenAI"""
        value_analysis = scoring_data.get('value_analysis', {})
        
        prompt = f"""Analyze this property investment data and provide a detailed analysis using the following markdown format:

# Overall Assessment

The property scored **{scoring_data['total_score']}/100** with a **{scoring_data['confidence']}** confidence level.

Current estimated value: **${value_analysis.get('estimated_value', 0):,.2f}**
Value range: ${value_analysis.get('value_range_low', 0):,.2f} to ${value_analysis.get('value_range_high', 0):,.2f}

Provide a concise summary of the overall investment opportunity.

## Market Analysis 🏘️

* Market Value: ${scoring_data['market_context'].get('avg_value', 0):,.2f}
* Price/SqFt: ${scoring_data['market_context'].get('avg_price_sqft', 0):,.2f}
* Market Activity: {scoring_data['market_context'].get('avg_days_on_market', 0):.0f} days average
* Total Properties: {scoring_data['market_context'].get('total_properties', 0)}

Analyze these market metrics and their implications.

## Investment Potential 📈

Score Breakdown:
* 💰 Value Score: {scoring_data['value_score']}/40
* 📍 Location Score: {scoring_data['location_score']}/30
* ⭐ Feature Score: {scoring_data['feature_score']}/30

Key Factors:
{chr(10).join(f"* {factor}" for factor in scoring_data['factors'])}

## Property Features 🏠

Analyze the property's strengths and potential improvements based on:
{chr(10).join(f"* {factor}" for factor in scoring_data['factors'])}

## Risk Analysis ⚠️

Consider:
* Market-specific risks
* Property-specific concerns
* Competition factors
* Price position relative to market

## Recommendations 📋

1. **Price Strategy**
   * Current ask vs. market value
   * Negotiation points
   * Value-add opportunities

2. **Next Steps**
   * Due diligence checklist
   * Key areas to investigate
   * Timeline considerations

Focus on clear, actionable insights structured with proper markdown formatting. Use bullet points for lists and bold for key metrics."""

        try:
            response = self.client.completions.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt,
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].text.strip()
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return "Unable to generate analysis at this time. Please try again later."