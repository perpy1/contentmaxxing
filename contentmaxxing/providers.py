"""One task contract shared by external agents and compatible model servers."""
import json
import os
import re
from typing import Any, Dict, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class Provider(Protocol):
    def generate(self, task: Dict[str, Any]) -> Dict[str, Any]: ...
    def analyze(self, task: Dict[str, Any]) -> Dict[str, Any]: ...
    def classify(self, task: Dict[str, Any]) -> Dict[str, Any]: ...
    def extract(self, task: Dict[str, Any]) -> Dict[str, Any]: ...


class PendingTask(Exception):
    def __init__(self, task_id):
        self.task_id = task_id
        super().__init__('External agent result required: ' + task_id)


class Operations:
    def analyze(self, task):
        return self.generate(task)

    def classify(self, task):
        return self.generate(task)

    def extract(self, task):
        return self.generate(task)


class ExternalProvider(Operations):
    """Export a self-contained task. No vendor runtime or hidden conversation needed."""
    def generate(self, task):
        raise PendingTask(task['id'])


class ExtractiveProvider(Operations):
    """Offline retrieval, explicitly not an AI writer or semantic transcript miner."""
    def generate(self, task):
        inputs = task['inputs']
        if task['operation'] == 'mine':
            ideas = []
            for number, line in enumerate(inputs['text'].splitlines(), inputs.get('source_window', {}).get('start_line', 1)):
                # Preserve exact wording/speaker, no cap, one candidate per substantive sentence.
                for sentence in re.split(r'(?<=[.!?])\s+', line.strip()):
                    if len(sentence.split()) >= 5:
                        ideas.append({'topic': sentence, 'quote': sentence, 'start_line': number,
                                      'end_line': number, 'category': 'source excerpt',
                                      'article_candidate': len(sentence.split()) >= 30})
            return {'ideas': ideas}
        if task['operation'] == 'draft':
            if inputs.get('revision_target'):
                raise ValueError('Extractive mode cannot apply editorial revisions. Use external or openai-compatible.')
            if inputs['platform'] not in ('x', 'linkedin', 'substack_note'):
                raise ValueError('Extractive mode cannot write native video/articles. Choose external or openai-compatible.')
            idea = inputs['idea']
            quote = idea['source_reference'][0]['quote']
            if inputs['platform'] == 'x' and idea['format'] not in ('long-form X post', 'Reddit-style breakdown') and len(quote) > inputs['x_max_chars']:
                raise ValueError('Source excerpt exceeds short X limit; choose a long format or a generative provider.')
            return {'body': quote, 'title': idea['topic'], 'claims': [], 'framework': None,
                    'quality_notes': ['Literal source excerpt; native writing and voice review required.',
                                      'Verify speaker attribution and source consent before publication.']}
        raise ValueError('Extractive provider does not implement ' + task['operation'])


def http_json(method, url, headers, body=None):
    payload = None if body is None else json.dumps(body, allow_nan=False).encode('utf-8')
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as exc:
        # Do not echo upstream bodies: those can contain prompts or credentials.
        raise ValueError('Remote API HTTP %s; check credentials/capabilities/rate limits. No automatic mutation retry.' % exc.code) from None
    except (URLError, TimeoutError):
        raise ValueError('Remote API unavailable; use external-agent or export/manual mode.') from None


class OpenAICompatibleProvider(Operations):
    def __init__(self, base_url, model, api_key, transport=http_json):
        if not model:
            raise ValueError('Set model in config.yaml for openai-compatible execution.')
        url = urlsplit(base_url)
        allowed = url.scheme == 'https' or (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1', '::1'))
        if not allowed or not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment:
            raise ValueError('Model URL must use HTTPS, or HTTP on localhost.')
        url.port  # Validate malformed or out-of-range ports before attempting transport.
        self.base_url, self.model, self.api_key, self.transport = base_url.rstrip('/'), model, api_key, transport

    def generate(self, task):
        result = self.transport('POST', self.base_url + '/chat/completions',
                                {'Authorization': 'Bearer ' + self.api_key, 'Content-Type': 'application/json'},
                                {'model': self.model, 'messages': [
                                    {'role': 'system', 'content': task['instructions']},
                                    {'role': 'user', 'content': json.dumps({'inputs': task['inputs'],
                                                                         'output_contract': task['output_contract']}, ensure_ascii=False)}]})
        try:
            choice = result['choices'][0]
            if choice.get('finish_reason') in ('length', 'content_filter'):
                raise ValueError('Model response incomplete or filtered; task remains pending.')
            output = json.loads(choice['message']['content'])
            if not isinstance(output, dict):
                raise ValueError('Model response must be a JSON object.')
            return output
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ValueError('Model returned an invalid JSON response; task remains pending.') from None


def provider_from(config, override=None):
    name = override or config['provider']
    if name == 'external':
        return ExternalProvider()
    if name == 'extractive':
        return ExtractiveProvider()
    if name == 'openai-compatible':
        key = os.environ.get(config['api_key_env'], '')
        return OpenAICompatibleProvider(config['base_url'], config['model'], key)
    raise ValueError('Unknown provider: ' + name)
