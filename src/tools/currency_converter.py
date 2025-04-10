import os
from dotenv import load_dotenv
import requests
from typing import Dict, Any, Optional

# Load environment variables from .env file in the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

def convert_currency(amount: float, source_currency: str, target_currency: str) -> Dict[str, Any]:
    """Converts an amount from one currency to another using the Exchange Rates API.

    Parameters:
        amount: The amount to convert
        source_currency: The source currency code (e.g., "USD", "EUR", "RUB")
        target_currency: The target currency code (e.g., "USD", "EUR", "RUB")

    Returns:
        A dictionary containing the conversion result with the following keys:
        - amount: The original amount
        - source_currency: The source currency code
        - target_currency: The target currency code
        - rate: The exchange rate used
        - result: The converted amount
    """
    try:
        api_key = os.getenv("EXCHANGE_RATE_API_KEY")
        if not api_key:
            return {
                'error': 'EXCHANGE_RATE_API_KEY environment variable is not set',
                'amount': amount,
                'source_currency': source_currency,
                'target_currency': target_currency,
                'result': None
            }

        base_url = "https://v6.exchangerate-api.com/v6"
        url = f"{base_url}/{api_key}/pair/{source_currency}/{target_currency}/{amount}"

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        return {
            'result': data['conversion_result'],
            'amount': amount,
            'source_currency': source_currency,
            'target_currency': target_currency
        }

    except requests.exceptions.RequestException as e:
        return {
            'error': f'API request failed: {str(e)}',
            'amount': amount,
            'source_currency': source_currency,
            'target_currency': target_currency,
            'result': None
        }
    except (KeyError, ValueError) as e:
        return {
            'error': f'Failed to parse API response: {str(e)}',
            'amount': amount,
            'source_currency': source_currency,
            'target_currency': target_currency,
            'result': None
        }