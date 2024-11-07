import os
import requests
import logging
from typing import Dict, Optional, List, Union
from time import sleep
from dotenv import load_dotenv
import json
import re

class RentcastAPI:
    def __init__(self):
        """Initialize RentcastAPI with API key from environment"""
        load_dotenv()
        self.api_key = os.getenv('RENTCAST_API_KEY')
        if not self.api_key:
            raise ValueError("RENTCAST_API_KEY not found in environment variables")
            
        self.base_url = "https://api.rentcast.io/v1"
        self.headers = {
            "accept": "application/json",
            "X-Api-Key": self.api_key
        }
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with error handling and rate limiting"""
        try:
            self.logger.info(f"Making request to {endpoint} with params: {params}")
            
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            self.logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code == 404:
                self.logger.warning("Resource not found")
                return None
            
            if response.status_code != 200:
                self.logger.error(f"API error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            self.logger.info(f"Raw API Response: {json.dumps(data, indent=2)}")
            return data
            
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out")
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error occurred")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return None
        except ValueError as e:
            self.logger.error(f"JSON decode error: {e}")
            return None

    def get_property_data(self, address: str) -> Optional[Dict]:
        """Get property data by address"""
        if not address or not isinstance(address, str):
            self.logger.error("Invalid address provided")
            return None
            
        # Format address to match API expectations
        formatted_address = self.format_address(address)
        self.logger.info(f"Formatted address: {formatted_address}")
        
        params = {
            "address": formatted_address
        }
        
        data = self._make_request("/properties", params)
        
        if data and isinstance(data, list) and len(data) > 0:
            property_data = data[0]
            self.logger.info(f"Property data retrieved for: {formatted_address}")
            if self.validate_data(property_data):
                return property_data
            else:
                self.logger.warning("Property data missing required fields")
        else:
            self.logger.warning("No property data found or invalid response format")
        
        return None

    def get_value_estimate(self, address: str, property_data: Dict) -> Optional[Dict]:
        """Get property value estimate from AVM endpoint"""
        if not address:
            self.logger.error("No address provided for value estimate")
            return None
            
        # Format address consistently
        formatted_address = self.format_address(address)
        
        params = {
            "address": formatted_address,
            "propertyType": property_data.get('propertyType', 'Single Family'),
            "bedrooms": property_data.get('bedrooms'),
            "bathrooms": property_data.get('bathrooms'),
            "squareFootage": property_data.get('squareFootage'),
            "compCount": 5  # Start with 5 comps for MVP
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        self.logger.info(f"Requesting value estimate for: {formatted_address}")
        data = self._make_request("/avm/value", params)
        
        if data:
            self.logger.info(f"Received value estimate: ${data.get('price', 0):,}")
            return data
            
        self.logger.warning("No value estimate received")
        return None

    def get_market_data(self, zip_code: str) -> Optional[Dict]:
        """Get market data for a zip code"""
        if not zip_code or not zip_code.isdigit() or len(zip_code) != 5:
            self.logger.error("Invalid zip code format")
            return None
            
        params = {
            "zipCode": zip_code,
            "dataType": "All",  # Get both sale and rental data
            "historyRange": 12  # Get 12 months of history
        }
        
        data = self._make_request("/markets", params)
        
        if data:
            self.logger.info(f"Market data retrieved for zip code: {zip_code}")
            
            # If we don't have sale data but have rental data, create a minimal sale data structure
            if 'rentalData' in data and 'saleData' not in data:
                rental_data = data['rentalData']
                data['saleData'] = {
                    'lastUpdatedDate': rental_data.get('lastUpdatedDate'),
                    'averagePrice': 0,  # We'll rely more on the AVM endpoint
                    'totalListings': rental_data.get('totalListings', 0),
                    'averageSquareFootage': rental_data.get('averageSquareFootage', 0),
                    'averageDaysOnMarket': rental_data.get('averageDaysOnMarket', 0)
                }
                self.logger.info("Created minimal sale data structure from rental data")
        
        return data

    def get_comparables(self, address: str, zip_code: str) -> Optional[List[Dict]]:
        """Get comparable properties in the area"""
        if not address or not zip_code:
            self.logger.error("Missing address or zip code for comparables")
            return None
            
        params = {
            "address": address,
            "zipCode": zip_code,
            "radius": 1,    # 1 mile radius
            "limit": 5      # Top 5 comparables
        }
        
        data = self._make_request("/properties", params)
        
        if isinstance(data, list):
            valid_comps = [
                prop for prop in data 
                if self.validate_data(prop)
            ]
            
            self.logger.info(f"Found {len(valid_comps)} valid comparable properties")
            return valid_comps[:5]  # Return top 5 valid comparables
            
        return None

    def validate_data(self, property_data: Dict) -> bool:
        """Validate property data with detailed logging"""
        if not isinstance(property_data, dict):
            self.logger.error("Property data is not a dictionary")
            return False
            
        required_fields = [
            'bedrooms', 'bathrooms', 'squareFootage', 
            'yearBuilt', 'zipCode'
        ]
        
        missing_fields = [
            field for field in required_fields 
            if field not in property_data
        ]
        
        if missing_fields:
            self.logger.warning(f"Missing required fields: {', '.join(missing_fields)}")
            return False
            
        # Additional validation for field values
        if not all(str(property_data.get(field)) for field in required_fields):
            self.logger.warning("One or more required fields have empty values")
            return False
            
        return True

    def format_address(self, address: str) -> str:
        """Format address to match RentCast API expectations"""
        # Remove any extra whitespace
        address = ' '.join(address.split())
        
        # Extract zip code
        zip_match = re.search(r'\b\d{5}\b', address)
        if not zip_match:
            self.logger.warning("No zip code found in address")
            return address
        
        # Split address into components
        parts = address.split(',')
        if len(parts) >= 3:
            street = parts[0].strip()
            city = parts[1].strip()
            state_zip = parts[2].strip()
            
            # Format state and zip
            state_parts = state_zip.split()
            if len(state_parts) >= 2:
                state = state_parts[0].strip().upper()
                zip_code = zip_match.group(0)
                
                # Reconstruct address in correct format
                formatted = f"{street}, {city}, {state} {zip_code}"
                self.logger.info(f"Reformatted address: {formatted}")
                return formatted
        
        self.logger.warning("Could not parse address components, returning original")
        return address