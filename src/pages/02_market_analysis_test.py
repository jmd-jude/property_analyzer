import streamlit as st
from api.rentcast import RentcastAPI
from datetime import datetime, timedelta, timezone
import statistics
import pandas as pd

st.set_page_config(page_title="Market Analysis Test", layout="wide")

# Test addresses we know exist in RentCast's database
TEST_ADDRESSES = {
    "San Antonio (Suburban)": "4190 Sunrise Creek Dr, San Antonio, TX 78244",
    "East Austin (Urban/Hot)": "1000 E 5th St, Austin, TX 78702",
    "San Antonio Downtown (Urban/Condo)": "215 Center St, San Antonio, TX 78202",
    "Dallas Uptown": "3111 Cole Ave, Dallas, TX 75204",
    "Austin East Side": "1910 E 2nd St, Austin, TX 78702",
    "San Antonio Hills": "5914 Burning Sunrise Dr, San Antonio, TX 78244"
}

class MarketAnalyzer:
    def __init__(self):
        self.rentcast = RentcastAPI()

    def get_comparables(self, property_data, radius, sqft_range):
        """Get comparable properties using AVM endpoint"""
        params = {
            "address": property_data['formattedAddress'],
            "propertyType": property_data['propertyType'],
            "bedrooms": property_data['bedrooms'],
            "bathrooms": property_data['bathrooms'],
            "squareFootage": property_data['squareFootage'],
            "radius": radius,
            "compCount": 20  # Request more comps for better filtering
        }
        
        with st.expander("View Search Parameters"):
            st.json(params)
        
        avm_data = self.rentcast.get_value_estimate(params['address'], property_data)
        
        if avm_data and 'comparables' in avm_data:
            comps = avm_data['comparables']
            
            # Filter by square footage range
            sqft = property_data['squareFootage']
            min_sqft = sqft * (1 - sqft_range/100)
            max_sqft = sqft * (1 + sqft_range/100)
            
            filtered_comps = [
                comp for comp in comps
                if min_sqft <= comp['squareFootage'] <= max_sqft
            ]
            
            # Store value estimate in session state
            st.session_state.value_estimate = {
                'price': avm_data.get('price'),
                'low': avm_data.get('priceRangeLow'),
                'high': avm_data.get('priceRangeHigh')
            }
            
            return avm_data
        
        return None

    def get_rental_analysis(self, property_data, radius):
        """Get rental analysis using AVM rent endpoint"""
        try:
            rental_data = self.rentcast.get_rent_estimate(
                property_data['formattedAddress'],
                property_data
            )
            return rental_data
        except Exception as e:
            st.warning(f"Could not fetch rental data: {str(e)}")
            return None

    def calculate_tax_trends(self, tax_data):
        """Calculate tax assessment trends and metrics"""
        if not tax_data:
            return None
            
        years = sorted(tax_data.keys())
        if not years:
            return None
            
        trends = {
            'years': years,
            'total_values': [tax_data[year]['value'] for year in years],
            'land_values': [tax_data[year].get('land', 0) for year in years],
            'improvement_values': [tax_data[year].get('improvements', 0) for year in years]
        }
        
        # Calculate year-over-year changes
        if len(years) > 1:
            latest_value = tax_data[years[-1]]['value']
            oldest_value = tax_data[years[0]]['value']
            years_diff = float(years[-1]) - float(years[0])
            annual_appreciation = ((latest_value/oldest_value) ** (1/years_diff) - 1) * 100
            trends['annual_appreciation'] = annual_appreciation
            
        return trends

    def display_property_details(self, property_data):
        """Display basic property information"""
        st.subheader("Target Property")
        cols = st.columns(6)
        cols[0].metric("Type", property_data.get('propertyType', 'N/A'))
        cols[1].metric("Beds", property_data.get('bedrooms', 'N/A'))
        cols[2].metric("Baths", property_data.get('bathrooms', 'N/A'))
        cols[3].metric("SqFt", f"{property_data.get('squareFootage', 0):,}")
        cols[4].metric("Year Built", property_data.get('yearBuilt', 'N/A'))
        cols[5].metric("Lot Size", f"{property_data.get('lotSize', 0):,}")

        if property_data.get('features'):
            with st.expander("Property Features"):
                fcols = st.columns(3)
                features = property_data['features']
                for i, (key, value) in enumerate(features.items()):
                    fcols[i % 3].write(f"**{key.title()}:** {str(value)}")

    def analyze_property(self, address, radius, sqft_range):
        """Complete property analysis with value, rental, and tax data"""
        
        # Get base property data
        property_data = self.rentcast.get_property_data(address)
        if not property_data:
            st.error(f"Could not fetch property data for {address}")
            return None
            
        # Display property details
        self.display_property_details(property_data)
        
        # Value Analysis
        st.subheader("Value Analysis")
        value_data = self.get_comparables(property_data, radius, sqft_range)
        
        if value_data:
            cols = st.columns(3)
            cols[0].metric("Estimated Value", f"${value_data.get('price', 0):,.0f}")
            cols[1].metric(
                "Value Range", 
                f"${value_data.get('priceRangeLow', 0):,.0f} - ${value_data.get('priceRangeHigh', 0):,.0f}"
            )
            spread = ((value_data.get('priceRangeHigh', 0) - value_data.get('priceRangeLow', 0)) 
                     / value_data.get('price', 1)) * 100
            cols[2].metric("Value Spread", f"{spread:.1f}%")
            
            # Sales Comps Analysis
            if 'comparables' in value_data:
                st.subheader("Sales Comparables")
                comps = value_data['comparables']
                recent_comps = [
                    comp for comp in comps 
                    if comp.get('lastSeenDate') and 
                    datetime.fromisoformat(comp['lastSeenDate'].replace('Z', '+00:00')) >
                    datetime.now(timezone.utc) - timedelta(days=180)
                ]
                
                # Comp Summary Metrics
                metric_cols = st.columns(4)
                metric_cols[0].metric("Total Comps", len(comps))
                metric_cols[1].metric("Recent Sales", len(recent_comps))
                
                avg_correlation = statistics.mean(
                    float(c.get('correlation', 0)) for c in comps
                ) if comps else 0
                metric_cols[2].metric(
                    "Avg Similarity",
                    f"{avg_correlation*100:.1f}%"
                )
                
                avg_distance = statistics.mean(
                    float(c.get('distance', 0)) for c in comps
                ) if comps else 0
                metric_cols[3].metric(
                    "Avg Distance",
                    f"{avg_distance:.2f} mi"
                )
                
                # Display Individual Comps
                for comp in sorted(comps, key=lambda x: float(x.get('correlation', 0)), reverse=True):
                    with st.expander(
                        f"📍 {comp['formattedAddress']} - {float(comp.get('correlation', 0))*100:.1f}% Similar"
                    ):
                        cols = st.columns(4)
                        cols[0].write(f"**Price:** ${comp.get('price', 0):,.0f}")
                        cols[1].write(f"**$/SqFt:** ${comp.get('price', 0)/comp['squareFootage']:.0f}")
                        cols[2].write(f"**Distance:** {comp.get('distance', 'N/A')} miles")
                        cols[3].write(f"**Days on Market:** {comp.get('daysOnMarket', 'N/A')}")
                        
                        # Additional details
                        detail_cols = st.columns(4)
                        detail_cols[0].write(f"**Beds:** {comp.get('bedrooms', 'N/A')}")
                        detail_cols[1].write(f"**Baths:** {comp.get('bathrooms', 'N/A')}")
                        detail_cols[2].write(f"**SqFt:** {comp.get('squareFootage', 'N/A'):,}")
                        detail_cols[3].write(f"**Year Built:** {comp.get('yearBuilt', 'N/A')}")
        
        # Rental Analysis
        st.subheader("Rental Analysis")
        rental_data = self.get_rental_analysis(property_data, radius)
        
        if rental_data:
            cols = st.columns(4)
            cols[0].metric("Estimated Rent", f"${rental_data.get('rent', 0):,.0f}/mo")
            cols[1].metric(
                "Rent Range", 
                f"${rental_data.get('rentRangeLow', 0):,.0f} - ${rental_data.get('rentRangeHigh', 0):,.0f}"
            )
            
            # Calculate rent spread
            rent_spread = ((rental_data.get('rentRangeHigh', 0) - rental_data.get('rentRangeLow', 0)) 
                          / rental_data.get('rent', 1)) * 100
            cols[2].metric("Rent Spread", f"{rent_spread:.1f}%")
            
            # Calculate GRM
            if value_data and value_data.get('price') and rental_data.get('rent'):
                grm = value_data['price'] / (rental_data['rent'] * 12)
                cols[3].metric("Gross Rent Multiplier", f"{grm:.2f}")
            
            # Show rental comps
            if 'comparables' in rental_data:
                st.subheader("Rental Comparables")
                for comp in sorted(
                    rental_data['comparables'], 
                    key=lambda x: float(x.get('correlation', 0)), 
                    reverse=True
                ):
                    with st.expander(
                        f"📍 {comp['formattedAddress']} - {float(comp.get('correlation', 0))*100:.1f}% Similar"
                    ):
                        cols = st.columns(4)
                        cols[0].write(f"**Rent:** ${comp.get('price', 0):,.0f}/mo")
                        cols[1].write(f"**$/SqFt/Mo:** ${comp.get('price', 0)/comp['squareFootage']:.2f}")
                        cols[2].write(f"**Distance:** {comp.get('distance', 'N/A')} miles")
                        cols[3].write(f"**Days on Market:** {comp.get('daysOnMarket', 'N/A')}")
        
        # Tax Assessment Analysis
        if 'taxAssessments' in property_data:
            st.subheader("Tax Assessment History")
            tax_trends = self.calculate_tax_trends(property_data['taxAssessments'])
            
            if tax_trends:
                tax_df = pd.DataFrame({
                    'Year': tax_trends['years'],
                    'Total Value': [f"${v:,.0f}" for v in tax_trends['total_values']],
                    'Land Value': [f"${v:,.0f}" for v in tax_trends['land_values']],
                    'Improvement Value': [f"${v:,.0f}" for v in tax_trends['improvement_values']]
                })
                st.table(tax_df)
                
                cols = st.columns(3)
                latest_year = tax_trends['years'][-1]
                cols[0].metric(
                    "Current Assessment", 
                    f"${property_data['taxAssessments'][latest_year]['value']:,.0f}"
                )
                
                if 'annual_appreciation' in tax_trends:
                    cols[1].metric(
                        "Avg Annual Appreciation", 
                        f"{tax_trends['annual_appreciation']:.1f}%"
                    )
                
                # Calculate current ratio
                if value_data and value_data.get('price'):
                    assessment_ratio = value_data['price'] / property_data['taxAssessments'][latest_year]['value']
                    cols[2].metric("Value/Assessment Ratio", f"{assessment_ratio:.2f}")
                
                # Plot assessment trends
                st.line_chart(tax_df.set_index('Year'))
        
        # Investment Quality Metrics
        if value_data and rental_data and 'taxAssessments' in property_data:
            st.subheader("Investment Quality Metrics")
            cols = st.columns(4)
            
            # Annual Return Metrics
            if rental_data.get('rent'):
                annual_yield = (rental_data['rent'] * 12 / value_data['price']) * 100
                cols[0].metric("Gross Rental Yield", f"{annual_yield:.1f}%")
            
            # Market Position
            if value_data.get('comparables'):
                price_per_sqft = value_data['price'] / property_data['squareFootage']
                comp_ppsf = [c['price']/c['squareFootage'] for c in value_data['comparables']]
                percentile = sum(1 for x in comp_ppsf if x < price_per_sqft) / len(comp_ppsf) * 100
                cols[1].metric("Market Position ($/SqFt)", f"{percentile:.0f}th percentile")
            
            # Value Stability
            stability_score = 100 - (spread/2 + rent_spread/2)  # Simple example
            cols[2].metric("Stability Score", f"{stability_score:.0f}/100")
            
            # Liquidity Score
            if value_data.get('comparables'):
                avg_dom = statistics.mean(
                    float(c.get('daysOnMarket', 0)) for c in value_data['comparables'] if c.get('daysOnMarket')
                )
                liquidity_score = max(0, 100 - (avg_dom/2))  # Simple example
                cols[3].metric("Liquidity Score", f"{liquidity_score:.0f}/100")

def main():
    st.title("Market Analysis Test Page")
    st.write("Testing new market analysis with adjustable filtering")
    
    # Initialize session state
    if 'radius' not in st.session_state:
        st.session_state.radius = 2
    if 'sqft_range' not in st.session_state:
        st.session_state.sqft_range = 30

    # Create form for inputs
    with st.form("analysis_form"):
        # Address selector
        selected_market = st.selectbox(
            "Select Test Market",
            options=list(TEST_ADDRESSES.keys()),
            help="Choose a test property in different market types"
        )
        
        # Show the actual address that will be analyzed
        st.info(f"Will analyze: {TEST_ADDRESSES[selected_market]}")
        
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
        analyzer = MarketAnalyzer()
        analyzer.analyze_property(
            TEST_ADDRESSES[selected_market],
            st.session_state.radius,
            st.session_state.sqft_range
        )

if __name__ == "__main__":
    main()