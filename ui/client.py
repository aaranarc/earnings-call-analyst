"""Streamlit's Python server calls FastAPI; the browser never receives the API token."""
import json
import os

import httpx


class AnalystError(Exception):
    """A safe message that can be displayed without leaking credentials."""


def health():
    try:
        response = httpx.get(os.getenv('API_ORIGIN', 'http://127.0.0.1:8000').rstrip('/') + '/health', timeout=5)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return {'status': 'unreachable', 'configured': False}


def ask(question, on_status=lambda message: None, transport=None):
    origin = os.getenv('API_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
    token = os.getenv('API_ACCESS_TOKEN', '')
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    timeout = httpx.Timeout(290, connect=10)
    try:
        with (httpx.Client(timeout=timeout, transport=transport) as client,
              client.stream('POST', origin + '/ask', json={'question': question}, headers=headers) as response):
            if response.status_code != 200:
                messages = {401: 'API access denied. Check the server token.',
                            422: 'Enter a question between 3 and 2,000 characters.',
                            429: 'The analyst is busy or the daily request limit is reached. Retry later.',
                            503: 'The analyst is not configured or is waking up. Retry shortly.'}
                raise AnalystError(messages.get(response.status_code, 'The analyst is unavailable. Please retry.'))
            event, data = '', []
            for line in response.iter_lines():
                if line.startswith('event:'):
                    event = line[6:].strip()
                elif line.startswith('data:'):
                    data.append(line[5:].lstrip())
                elif not line and data:
                    payload = json.loads('\n'.join(data))
                    if event == 'status':
                        on_status(str(payload))
                    elif event == 'answer' and isinstance(payload, dict):
                        return payload
                    elif event == 'error':
                        raise AnalystError('The analyst could not finish. Please retry or inspect a dated example.')
                    event, data = '', []
    except (httpx.HTTPError, ValueError) as exc:
        raise AnalystError('Cannot reach the analyst. Start the API or wait for it to wake, then retry.') from exc
    raise AnalystError('The connection ended before an answer arrived. Please retry.')


def check_research(symbol, thesis, periods, transport=None):
    """Ask for reviewed quote suggestions; never change a saved assessment automatically."""
    origin = os.getenv('API_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
    token = os.getenv('API_ACCESS_TOKEN', '')
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    try:
        with httpx.Client(timeout=httpx.Timeout(290, connect=10), transport=transport) as connection:
            response = connection.post(origin + '/thesis/check',
                json={'symbol': symbol, 'thesis': thesis, 'periods': periods}, headers=headers)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AnalystError('The research check is unavailable. Choose covered periods, check API configuration and retry.') from exc
