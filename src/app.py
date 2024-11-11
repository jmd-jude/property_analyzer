import streamlit as st
from api.rentcast import RentcastAPI
from datetime import datetime, timedelta, timezone
import statistics
import pandas as pd
from api.openai_service import OpenAIService

st.set_page_config(page_title="Property Analysis", layout="wide")

class MarketAnalyzer:
    def __init__(self):
        self.rentcast = RentcastAPI()
        self.openai = OpenAIService()

    def colored_metric(self, label, value, help_text, thresholds=None, format_func=None):
        """
        Display a metric with color coding based on thresholds
        thresholds: dict with 'good', 'medium', 'poor' keys and their threshold values
        format_func: function to format the value (e.g., lambda x: f"${x:,.0f}")
        """
        if format_func:
            formatted_value = format_func(value)
        else:
            formatted_value = value
            
        if thresholds:
            if value <= thresholds.get('poor', float('inf')):
                formatted_value = f"🔴 {formatted_value}"
            elif value <= thresholds.get('medium', float('inf')):
                formatted_value = f"🟡 {formatted_value}"
            else:
                formatted_value = f"🟢 {formatted_value}"
                
        return formatted_value, help_text
    
    def display_property_details(self, property_data):
        """Display basic property information"""
        st.subheader("Property Details")
        cols = st.columns(6)
        cols[0].metric("Type", property_data.get('propertyType', 'N/A'))
        cols[1].metric("Beds", property_data.get('bedrooms', 'N/A'))
        cols[2].metric("Baths", property_data.get('bathrooms', 'N/A'))
        cols[3].metric("SqFt", f"{property_data.get('squareFootage', 0):,}")
        cols[4].metric("Year Built", property_data.get('yearBuilt', 'N/A'))
        cols[5].metric("Lot Size", f"{property_data.get('lotSize', 0):,}")

    def display_value_analysis(self, value_data, property_data):
        """Display value analysis metrics"""
        if value_data:
            cols = st.columns(3)
            cols[0].metric(
                "Estimated Value", 
                f"${value_data.get('price', 0):,.0f}",
                help="Estimated market value based on recent comparable sales"
            )
            cols[1].metric(
                "Value Range", 
                f"${value_data.get('priceRangeLow', 0):,.0f} - ${value_data.get('priceRangeHigh', 0):,.0f}",
                help="Expected value range based on market variability and comp quality"
            )
            spread = ((value_data.get('priceRangeHigh', 0) - value_data.get('priceRangeLow', 0)) 
                    / value_data.get('price', 1)) * 100
            cols[2].metric(
                "Value Spread", 
                f"{spread:.1f}%",
                help="Lower spread indicates higher confidence in the value estimate"
            )

    def display_income_metrics(self, value_data, rental_data, property_data):
        """Display income property focused metrics with color coding"""
        if value_data and rental_data:
            cols = st.columns(4)
            
            # Monthly Rent
            monthly_rent = rental_data.get('rent', 0)
            annual_rent = monthly_rent * 12
            cols[0].metric(
                "Monthly Rent",
                *self.colored_metric(
                    "Monthly Rent",
                    monthly_rent,
                    "Estimated monthly rental income based on comparable properties",
                    format_func=lambda x: f"${x:,.0f}"
                )
            )
            
            # Gross Rent Multiplier
            if value_data.get('price'):
                grm = value_data['price'] / annual_rent
                cols[1].metric(
                    "Gross Rent Multiplier",
                    *self.colored_metric(
                        "GRM",
                        grm,
                        "Property price divided by annual rent. Lower is better. Under 15x is considered good.",
                        thresholds={'poor': 20, 'medium': 15, 'good': 12},
                        format_func=lambda x: f"{x:.1f}x"
                    )
                )
            
            # Cap Rate
            noi = annual_rent * 0.6  # Simple NOI estimation
            if value_data.get('price'):
                cap_rate = (noi / value_data['price']) * 100
                cols[2].metric(
                    "Est. Cap Rate",
                    *self.colored_metric(
                        "Cap Rate",
                        cap_rate,
                        "Estimated net operating income divided by property value. Higher is better. 5-10% is typical.",
                        thresholds={'poor': 4, 'medium': 6, 'good': 8},
                        format_func=lambda x: f"{x:.1f}%"
                    )
                )
            
            # Price per Square Foot
            if property_data.get('squareFootage'):
                price_sqft = value_data['price'] / property_data['squareFootage']
                cols[3].metric(
                    "Price/SqFt",
                    *self.colored_metric(
                        "Price/SqFt",
                        price_sqft,
                        "Price per square foot. Compare to similar properties to gauge value.",
                        format_func=lambda x: f"${x:.0f}"
                    )
                )

    def display_exchange_metrics(self, value_data, property_data, comparables):
        """Display 1031 exchange focused metrics with color coding"""
        if value_data and comparables:
            cols = st.columns(4)
            
            # Market Velocity
            days_on_market = [c.get('daysOnMarket', 0) for c in comparables if c.get('daysOnMarket')]
            if days_on_market:
                median_dom = statistics.median(days_on_market)
                cols[0].metric(
                    "Median Days to Sell",
                    *self.colored_metric(
                        "DOM",
                        median_dom,
                        "Median time properties take to sell. Critical for 180-day exchange window.",
                        thresholds={'poor': 90, 'medium': 45, 'good': 30},
                        format_func=lambda x: f"{x:.0f}"
                    )
                )
                
                # Timeline Risk
                timeline_risk = "Low" if median_dom < 45 else "Medium" if median_dom < 90 else "High"
                risk_color = "🟢" if timeline_risk == "Low" else "🟡" if timeline_risk == "Medium" else "🔴"
                cols[1].metric(
                    "Timeline Risk",
                    f"{risk_color} {timeline_risk}",
                    "Risk assessment for meeting 1031 exchange deadlines based on market velocity"
                )
            
            # Like-Kind Confidence
            if property_data.get('propertyType') == 'Single Family':
                cols[2].metric(
                    "Like-Kind Status",
                    "🟢 Qualified",
                    "Indicates if property qualifies as like-kind for 1031 exchange purposes"
                )
            else:
                cols[2].metric(
                    "Like-Kind Status",
                    "🟡 Review Needed",
                    "Additional review needed to confirm like-kind qualification"
                )
            
            # Market Liquidity
            active_count = len([c for c in comparables if not c.get('removedDate')])
            cols[3].metric(
                "Active Listings",
                *self.colored_metric(
                    "Active",
                    active_count,
                    "Number of similar properties currently available. Important for 45-day identification period",
                    thresholds={'poor': 3, 'medium': 5, 'good': 10},
                    format_func=str
                )
            )

    def analyze_property(self, address, radius, sqft_range):
        """Complete property analysis with tabbed interface"""
        
        # Get base property data
        property_data = self.rentcast.get_property_data(address)
        if not property_data:
            st.error(f"Could not fetch property data for {address}")
            return None

        # Display property details at the top
        self.display_property_details(property_data)
        
        # Get value and rental data
        value_data = self.rentcast.get_value_estimate(address, property_data)
        rental_data = self.rentcast.get_rent_estimate(address, property_data)
        
        # Create tabs for different analysis views
        income_tab, exchange_tab = st.tabs(["Income Property Analysis", "1031 Exchange Analysis"])
        
        with income_tab:
            st.subheader("Value Analysis")
            self.display_value_analysis(value_data, property_data)
            
            st.subheader("Income Analysis")
            self.display_income_metrics(value_data, rental_data, property_data)
            
            if value_data and 'comparables' in value_data:
                st.subheader("Market Analysis")
                income_cols = st.columns(2)
                
                with income_cols[0]:
                    st.write("Recent Sales")
                    for comp in sorted(
                        value_data['comparables'], 
                        key=lambda x: float(x.get('correlation', 0)), 
                        reverse=True
                    )[:3]:
                        with st.expander(
                            f"📍 {comp['formattedAddress']} ({comp.get('correlation', 0)*100:.1f}% Similar)"
                        ):
                            ccols = st.columns(3)
                            ccols[0].write(f"**Price:** ${comp.get('price', 0):,.0f}")
                # Safely calculate price per square foot if squareFootage is available
                if comp.get('squareFootage'):
                    price_per_sqft = comp.get('price', 0) / comp.get('squareFootage', 1)
                    ccols[1].write(f"Price/SqFt: ${price_per_sqft:.0f}")
                else:
                    ccols[1].write("Price/SqFt: N/A")
                ccols[2].write(f"Days on Market: {comp.get('daysOnMarket', 'N/A')}")
                
                with income_cols[1]:
                    if rental_data and 'comparables' in rental_data:
                        st.write("Rental Comps")
                        for comp in sorted(
                            rental_data['comparables'], 
                            key=lambda x: float(x.get('correlation', 0)), 
                            reverse=True
                        )[:3]:
                            with st.expander(
                                f"📍 {comp['formattedAddress']} ({comp.get('correlation', 0)*100:.1f}% Similar)"
                            ):
                                rcols = st.columns(3)
                                rcols[0].write(f"**Rent:** ${comp.get('price', 0):,.0f}/mo")
            # Safely calculate price per square foot if squareFootage is available
            if comp.get('squareFootage'):
                price_per_sqft = comp.get('price', 0) / comp.get('squareFootage', 1)
                rcols[1].write(f"Price/SqFt: ${price_per_sqft:.2f}")
            else:
                rcols[1].write("Price/SqFt: N/A")
            rcols[2].write(f"Days on Market: {comp.get('daysOnMarket', 'N/A')}")

            if value_data and rental_data:
            # Prepare data for AI analysis
                analysis_data = {
                "propertyType": property_data.get('propertyType'),
                "bedrooms": property_data.get('bedrooms'),
                "bathrooms": property_data.get('bathrooms'),
                "squareFootage": property_data.get('squareFootage'),
                "yearBuilt": property_data.get('yearBuilt'),
                "value_estimate": value_data,
                "rental_estimate": rental_data,
                "grm": value_data['price'] / (rental_data['rent'] * 12) if rental_data.get('rent') else 0,
                "cap_rate": ((rental_data['rent'] * 12 * 0.6) / value_data['price']) * 100 if rental_data.get('rent') else 0,
                "market_metrics": {
                    "median_dom": statistics.median([c.get('daysOnMarket', 0) for c in value_data['comparables'] if c.get('daysOnMarket')]),
                    "avg_correlation": statistics.mean([float(c.get('correlation', 0)) for c in value_data['comparables']])
                }
            }
            
            with st.expander("🤖 AI Investment Analysis", expanded=True):
                with st.spinner("Generating investment analysis..."):
                    analysis = self.openai.generate_investment_analysis(analysis_data)
                    st.markdown(analysis)
        
        with exchange_tab:
            st.subheader("Exchange Qualification Analysis")
            self.display_exchange_metrics(value_data, property_data, value_data.get('comparables', []))
            
            st.subheader("Timeline Analysis")
            timeline_cols = st.columns(2)
            
            with timeline_cols[0]:
                st.write("45-Day Identification Period")
                if value_data and 'comparables' in value_data:
                    active_comps = [
                        c for c in value_data['comparables'] 
                        if not c.get('removedDate')
                    ]
                    st.metric("Available Properties", len(active_comps), help="Properties currently available that could qualify for your exchange")
                    
                    days_on_market = [
                        c.get('daysOnMarket', 0) 
                        for c in value_data['comparables'] 
                        if c.get('daysOnMarket')
                    ]
                    if days_on_market:
                        avg_dom = sum(days_on_market) / len(days_on_market)
                        st.metric("Avg Days on Market", f"{avg_dom:.0f}", help="Average time properties take to sell in this market")
            
            with timeline_cols[1]:
                st.write("180-Day Closing Period")
                if value_data and 'comparables' in value_data:
                    recent_sales = [
                        c for c in value_data['comparables']
                        if c.get('removedDate') and c.get('daysOnMarket', 0) < 180
                    ]
                    success_rate = len(recent_sales) / len(value_data['comparables']) * 100
                    st.metric("180-Day Close Rate", f"{success_rate:.0f}%", help="Percentage of properties that sold within 1031 exchange timeline requirements")
                    if 'taxAssessments' in property_data and property_data['taxAssessments']:
                        st.subheader("Value History")
                        tax_data = property_data['taxAssessments']
                        years = sorted(tax_data.keys())
                        if years:
                            df = pd.DataFrame({
                                'Year': years,
                                'Total Value': [tax_data[year]['value'] for year in years],
                            })
                            st.table(df.set_index('Year'))
            if value_data:
            # Prepare exchange-specific data
                exchange_data = {
                "propertyType": property_data.get('propertyType'),
                "value_estimate": value_data,
                "exchange_metrics": {
                    "available_properties": len([c for c in value_data['comparables'] if not c.get('removedDate')]),
                    "median_days_to_close": statistics.median([c.get('daysOnMarket', 0) for c in value_data['comparables'] if c.get('daysOnMarket')]),
                    "close_rate": (len([c for c in value_data['comparables'] if c.get('daysOnMarket', 180) < 180]) / len(value_data['comparables'])) * 100
                },
                "market_metrics": {
                    "median_dom": statistics.median([c.get('daysOnMarket', 0) for c in value_data['comparables'] if c.get('daysOnMarket')]),
                    "avg_correlation": statistics.mean([float(c.get('correlation', 0)) for c in value_data['comparables']])
                }
            }
            
            with st.expander("🤖 AI Exchange Analysis", expanded=True):
                with st.spinner("Generating 1031 exchange analysis..."):
                    analysis = self.openai.generate_1031_analysis(exchange_data)
                    st.markdown(analysis)

def main():
    st.title("Property Investment Analysis")
    st.write("Analyze properties for income potential or 1031 exchange qualification")
    
    # Initialize session state
    if 'radius' not in st.session_state:
        st.session_state.radius = 2
    if 'sqft_range' not in st.session_state:
        st.session_state.sqft_range = 30
    if 'address' not in st.session_state:
        st.session_state.address = ""

    # Create form for inputs
    with st.form("analysis_form"):
        col1, col2 = st.columns([2,1])
        
        with col1:
            address = st.text_input(
                "Enter the property address",
                value=st.session_state.address,
                help="Format: Street Address, City, State Zip (e.g., 123 Main St, Austin, TX 78702)",
                placeholder="123 Main St, Austin, TX 78702"
            )
        
        with col2:
            st.write("Need a test address?")
            if st.form_submit_button("Load Example"):
                st.session_state.address = "1000 E 5th St, Austin, TX 78702"
                st.rerun()
        
        st.subheader("Search Criteria")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.radius = st.slider(
                "Search Radius (miles)", 
                1, 5, 
                st.session_state.radius,
                help="Larger radius = more comps but less similar location"
            )
        with col2:
            st.session_state.sqft_range = st.slider(
                "Square Footage Range (%)", 
                20, 50, 
                st.session_state.sqft_range,
                help="Larger range = more comps but less similar size"
            )
            
        submitted = st.form_submit_button("Analyze Property")
        
        if submitted:
            if not address:
                st.error("Please enter a property address")
                return
                
            # Validate address format
            if "," not in address or len(address.split(",")) < 3:
                st.error("Please enter address in format: Street Address, City, State Zip")
                return
                
            # Check for zip code
            if not any(c.isdigit() for c in address.split(",")[-1]):
                st.error("Please include ZIP code in the address")
                return
                
            with st.spinner('Analyzing property...'):
                analyzer = MarketAnalyzer()
                analyzer.analyze_property(
                    address,
                    st.session_state.radius,
                    st.session_state.sqft_range
                )

if __name__ == "__main__":
    main()