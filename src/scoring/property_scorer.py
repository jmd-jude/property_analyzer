import logging
from typing import Dict, Optional
import re
from api.rentcast import RentcastAPI
from api.openai_service import OpenAIService

class PropertyScorer:
    def __init__(self):
        """Initialize scorer with API services"""
        self.rentcast = RentcastAPI()
        self.openai = OpenAIService()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def get_price_band(self, value: float) -> str:
        """Determine price band for property"""
        if value < 100000: return "Under 100K"
        elif value < 200000: return "100K-200K"
        elif value < 500000: return "200K-500K"
        return "Over 500K"

    def score_property(self, address: str, considered_price: float) -> Dict:
        """Calculate property score and generate insights"""
        score_breakdown = {
            'total_score': 0,
            'value_score': 0,
            'location_score': 0,
            'feature_score': 0,
            'confidence': 'low',
            'factors': [],
            'price_band': '',
            'market_context': {},
            'validation_examples': [],
            'value_analysis': {}
        }

        # Get property data
        property_data = self.rentcast.get_property_data(address)
        if not property_data:
            self.logger.error("Unable to fetch property data")
            return score_breakdown

        # Get value estimate
        value_estimate = self.rentcast.get_value_estimate(address, property_data)
        if value_estimate:
            score_breakdown['value_analysis'] = {
                'estimated_value': value_estimate['price'],
                'value_range_low': value_estimate['priceRangeLow'],
                'value_range_high': value_estimate['priceRangeHigh']
            }

            # Value Score (40 points)
            estimated_value = value_estimate['price']
            price_ratio = considered_price / estimated_value
            
            if 0.9 <= price_ratio <= 1.1:
                score_breakdown['value_score'] = 40
                score_breakdown['factors'].append("Purchase price aligns well with estimated value")
            elif 0.8 <= price_ratio <= 1.2:
                score_breakdown['value_score'] = 35
                score_breakdown['factors'].append("Purchase price reasonably aligned with estimated value")
            elif price_ratio < 0.9:
                score_breakdown['value_score'] = 30
                score_breakdown['factors'].append("Potential value opportunity - below estimated value")
            else:
                score_breakdown['value_score'] = 20
                score_breakdown['factors'].append("Purchase price significantly above estimated value")

            # Add value insight
            value_diff = abs(considered_price - estimated_value)
            value_diff_percent = (value_diff / estimated_value) * 100
            if considered_price > estimated_value:
                score_breakdown['factors'].append(
                    f"Consider negotiating - asking price is {value_diff_percent:.1f}% above estimated value"
                )
            elif considered_price < estimated_value:
                score_breakdown['factors'].append(
                    f"Potential equity - asking price is {value_diff_percent:.1f}% below estimated value"
                )

        # Get market data
        zip_code = property_data.get('zipCode')
        market_data = self.rentcast.get_market_data(zip_code)
        
        if market_data and 'saleData' in market_data:
            market_stats = market_data['saleData']
            
            # Store market context
            score_breakdown['market_context'] = {
                'avg_value': market_stats.get('averagePrice', 0),
                'avg_price_sqft': market_stats.get('averagePricePerSquareFoot', 0),
                'total_properties': market_stats.get('totalListings', 0),
                'avg_sqft': market_stats.get('averageSquareFootage', 0),
                'avg_days_on_market': market_stats.get('averageDaysOnMarket', 0)
            }

            # Location/Market Score (30 points)
            if property_data.get('squareFootage') and market_stats.get('averageSquareFootage'):
                size_ratio = property_data['squareFootage'] / market_stats['averageSquareFootage']
                if 0.8 <= size_ratio <= 1.2:
                    score_breakdown['location_score'] += 15
                    score_breakdown['factors'].append("Property size aligns with market average")
                elif 0.6 <= size_ratio <= 1.4:
                    score_breakdown['location_score'] += 10
                    score_breakdown['factors'].append("Property size reasonable for market")
                else:
                    score_breakdown['location_score'] += 5
                    score_breakdown['factors'].append("Unusual size for market")

            days_on_market = market_stats.get('averageDaysOnMarket', 0)
            if days_on_market <= 30:
                score_breakdown['location_score'] += 15
                score_breakdown['factors'].append("High-demand market area")
            elif days_on_market <= 60:
                score_breakdown['location_score'] += 10
                score_breakdown['factors'].append("Moderate market activity")
            else:
                score_breakdown['location_score'] += 5
                score_breakdown['factors'].append("Slower market activity")

        # Feature Score (30 points)
        feature_score = 0
        features = property_data.get('features', {})
        
        if features.get('garageSpaces', 0) > 1:
            feature_score += 8
            score_breakdown['factors'].append("Multiple garage spaces add value")
        if features.get('coolingType') == 'Central':
            feature_score += 6
            score_breakdown['factors'].append("Central cooling system")
        if features.get('heatingType') == 'Central':
            feature_score += 6
            score_breakdown['factors'].append("Central heating system")
        if features.get('floorCount', 1) > 1:
            feature_score += 5
            score_breakdown['factors'].append("Multiple floors")
        if features.get('pool'):
            feature_score += 5
            score_breakdown['factors'].append("Pool adds value")

        score_breakdown['feature_score'] = feature_score

        # Process comparables from value estimate
        if value_estimate and 'comparables' in value_estimate:
            score_breakdown['validation_examples'] = [{
                'formattedAddress': comp.get('formattedAddress', ''),
                'squareFootage': comp.get('squareFootage', 0),
                'bedrooms': comp.get('bedrooms', 0),
                'bathrooms': comp.get('bathrooms', 0),
                'price': comp.get('price', 0),
                'correlation': comp.get('correlation', 0),
                'daysOnMarket': comp.get('daysOnMarket', 0)
            } for comp in value_estimate['comparables'][:5]]

        # Calculate total score
        score_breakdown['total_score'] = (
            score_breakdown['value_score'] +
            score_breakdown['location_score'] +
            score_breakdown['feature_score']
        )

        # Set confidence level
        if value_estimate and market_data:
            score_breakdown['confidence'] = 'high'
        elif value_estimate or market_data:
            score_breakdown['confidence'] = 'medium'

        # Set price band
        score_breakdown['price_band'] = self.get_price_band(considered_price)

        # Generate AI analysis
        try:
            score_breakdown['ai_analysis'] = self.openai.generate_property_analysis(score_breakdown)
        except Exception as e:
            self.logger.error(f"Failed to generate AI analysis: {e}")
            score_breakdown['ai_analysis'] = "Unable to generate analysis at this time."

        return score_breakdown