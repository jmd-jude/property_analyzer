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

    def generate_investment_analysis(self, property_data: Dict) -> str:
        """Generate investment-focused analysis"""
        prompt = f"""You are an expert real estate investment analyst. Analyze this property data and provide actionable insights for an income property investor.

Property Details:
- Type: {property_data.get('propertyType')}
- Configuration: {property_data.get('bedrooms')} beds, {property_data.get('bathrooms')} baths, {property_data.get('squareFootage')} sqft
- Year Built: {property_data.get('yearBuilt')}

Valuation:
- Estimated Value: ${property_data.get('value_estimate', {}).get('price', 0):,.0f}
- Value Range: ${property_data.get('value_estimate', {}).get('priceRangeLow', 0):,.0f} to ${property_data.get('value_estimate', {}).get('priceRangeHigh', 0):,.0f}

Income Metrics:
- Monthly Rent: ${property_data.get('rental_estimate', {}).get('rent', 0):,.0f}
- Gross Rent Multiplier: {property_data.get('grm', 0):.1f}x
- Est. Cap Rate: {property_data.get('cap_rate', 0):.1f}%

Market Metrics:
- Median Days on Market: {property_data.get('market_metrics', {}).get('median_dom', 0)}
- Average Comp Correlation: {property_data.get('market_metrics', {}).get('avg_correlation', 0)*100:.1f}%

Provide a detailed investment analysis following this structure using markdown:

Focus on clear, actionable insights using proper spacing and formatting. Some guidelines:
- Use proper spacing between sentences for readability
- Format numbers with commas for thousands
- Use proper currency formatting (e.g., $1,000,000)
- Avoid running words together
- Use line breaks between sections

# Investment Opportunity Overview
Provide a concise summary of the investment opportunity, highlighting the most compelling aspects.

## Valuation Analysis 💰
Analyze the property's value proposition, price positioning, and negotiation opportunities.

## Income Potential 📈
Evaluate the rental income potential, market positioning, and income stability factors.

## Market Position 📊
Assess how this property compares to market comps and its competitive advantages/disadvantages.

## Risk Assessment ⚠️
Identify key risks and mitigating factors.

## Strategic Recommendations 🎯
1. Outline specific action items for due diligence
2. Suggest negotiation strategy
3. Recommend property improvements that could enhance value

Focus on actionable insights that would help an investor make a decision. Be direct about both opportunities and concerns."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # Using GPT-4 for better analysis
                messages=[{
                    "role": "system",
                    "content": "You are an expert real estate investment analyst providing actionable insights to investors."
                },
                {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.7
            )
            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return "Unable to generate analysis at this time. Please try again later."

    def generate_1031_analysis(self, property_data: Dict) -> str:
        """Generate 1031 exchange focused analysis"""
        prompt = f"""You are a 1031 exchange specialist. Analyze this property data and provide insights specific to 1031 exchange considerations.

Property Details:
- Type: {property_data.get('propertyType')}
- Value: ${property_data.get('value_estimate', {}).get('price', 0):,.0f}
- Market Days: {property_data.get('market_metrics', {}).get('median_dom', 0)}

Timeline Metrics:
- Available Properties: {property_data.get('exchange_metrics', {}).get('available_properties', 0)}
- Median Days to Close: {property_data.get('exchange_metrics', {}).get('median_days_to_close', 0)}
- 180-Day Close Rate: {property_data.get('exchange_metrics', {}).get('close_rate', 0)}%

Provide a 1031-focused analysis following this structure using markdown:

Focus on clear, actionable insights using proper spacing and formatting. Some guidelines:
- Use proper spacing between sentences for readability
- Format numbers with commas for thousands
- Use proper currency formatting (e.g., $1,000,000)
- Avoid running words together
- Use line breaks between sections

# 1031 Exchange Suitability Analysis

## Timeline Feasibility 📅
Evaluate the likelihood of meeting 45-day identification and 180-day closing requirements based on market metrics.

## Like-Kind Qualification 📋
Assess property's qualification as like-kind replacement and any potential concerns.

## Value Match Analysis 💵
Analyze value adequacy for exchange purposes and equity preservation.

## Market Liquidity Risk 📊
Evaluate market conditions affecting transaction timeline feasibility.

## Critical Recommendations 🎯
1. Specific action items for the 45-day period
2. Risk mitigation strategies
3. Timeline management recommendations

Focus on exchange-specific considerations and timeline-critical factors. Be direct about feasibility concerns and mitigation strategies."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{
                    "role": "system",
                    "content": "You are a 1031 exchange specialist providing critical insights for exchange transactions."
                },
                {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.7
            )
            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return "Unable to generate analysis at this time. Please try again later."