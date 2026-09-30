"""Local, read-only source retrieval with bounded excerpts and original citations."""
import hashlib
import math
import re
import unicodedata
from bisect import bisect_right
from collections import Counter


STOPWORDS = set('a an and are as at be by for from has have how i in is it of on or our that the this to was we what when with you your'.split())


def terms(text):
    return set(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold())) - STOPWORDS


def bounded_integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('%s must be an integer from %s to %s.' % (name, lower, upper))
    return value


class SourceLibrary:
    """No hidden index. IDs depend on captured text and offsets, never its folder."""

    def __init__(self, store):
        self.store = store
        self._documents = {}

    def document(self, source_id):
        if source_id not in self._documents:
            metadata = self.store.get('sources', source_id)
            lines = self.store.source_text(source_id).splitlines()
            text = '\n'.join(lines)
            starts, offset = [], 0
            for line in lines:
                starts.append(offset)
                offset += len(line) + 1
            self._documents[source_id] = (metadata, text, lines, starts)
        return self._documents[source_id]

    def passage(self, source_id, start, end):
        metadata, text, _, starts = self.document(source_id)
        quote = text[start:end]
        return {'source_id': source_id, 'source_sha256': metadata['sha256'],
                'passage_id': 'span_' + hashlib.sha256(
                    ('%s:%s:%s:%s' % (source_id, metadata['sha256'], start, end)).encode()).hexdigest()[:20],
                'start_line': bisect_right(starts, start),
                'end_line': bisect_right(starts, max(start, end - 1)),
                'start_offset': start, 'end_offset': end, 'quote': quote,
                'title': metadata['title'], 'kind': metadata['kind'], 'consent': metadata['consent']}

    def read(self, source_id, start_line, end_line, max_chars=12000):
        bounded_integer(max_chars, 'max_chars', 1, 200000)
        _, text, lines, starts = self.document(source_id)
        if type(start_line) is not int or type(end_line) is not int or not 1 <= start_line <= end_line <= len(lines):
            raise ValueError('Source line range is invalid.')
        start = starts[start_line - 1]
        end = starts[end_line - 1] + len(lines[end_line - 1])
        if end - start > max_chars:
            raise ValueError('Requested lines exceed max_chars; request fewer lines or explicitly raise the budget.')
        return self.passage(source_id, start, end)

    def chunks(self, source_id, size=1200):
        _, text, _, _ = self.document(source_id)
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                # Preserve words when possible, while still handling a giant line/token.
                boundaries = [m.end() for m in re.finditer(r'\s+', text[start + size // 2:end])]
                if boundaries:
                    end = start + size // 2 + boundaries[-1]
            if text[start:end].strip():
                yield self.passage(source_id, start, end)
            if end == len(text):
                break
            start = max(start + 1, end - min(160, size // 4))

    def search(self, query, source_ids=None, kind=None, limit=8, max_chars=12000):
        bounded_integer(limit, 'limit', 1, 100)
        bounded_integer(max_chars, 'max_chars', 128, 200000)
        query_terms = terms(query)
        if not query_terms:
            raise ValueError('Use at least one specific search term.')
        if source_ids is None:
            sources = self.store.list('sources')
        else:
            sources = [self.store.get('sources', identifier) for identifier in dict.fromkeys(source_ids)]
        sources = [s for s in sources if kind is None or s['kind'] == kind]
        passages = [p for s in sources for p in self.chunks(s['id'], min(1200, max_chars))]
        frequencies = Counter()
        tokens = []
        for passage in passages:
            found = terms(passage['quote'])
            tokens.append(found)
            frequencies.update(found & query_terms)
        candidates = []
        for passage, found in zip(passages, tokens):
            matched = query_terms & found
            if not matched:
                continue
            # Rare terms and coverage rank evidence; this is lexical retrieval,
            # not a probability, semantic search, or an editorial quality score.
            weight = sum(1 + math.log((1 + len(passages)) / (1 + frequencies[t])) for t in matched)
            weight *= len(matched) / len(query_terms)
            candidates.append({**passage, 'score': round(weight, 6), 'matched_terms': sorted(matched)})
        candidates.sort(key=lambda p: (-p['score'], p['source_id'], p['start_offset']))
        selected, used = [], 0
        for passage in candidates:
            if len(selected) == limit:
                break
            if any(self.overlap(passage, old) for old in selected):
                continue
            if used + len(passage['quote']) > max_chars:
                continue
            selected.append(passage)
            used += len(passage['quote'])
        return {'query': query, 'method': 'lexical', 'source_count': len(sources),
                'matching_passages': len(candidates), 'returned_chars': used,
                'max_chars': max_chars, 'results': selected,
                'notice': 'Matches are evidence candidates, not proof of a claim. Check speaker, consent and surrounding context.'}

    @staticmethod
    def overlap(left, right):
        return left['source_id'] == right['source_id'] and max(left['start_offset'], right['start_offset']) < min(left['end_offset'], right['end_offset'])

    def required_passages(self, references):
        spans = {}
        for ref in references:
            self.store.validate_reference(ref)
            _, text, lines, starts = self.document(ref['source_id'])
            quote = ref['quote'].replace('\r\n', '\n').replace('\r', '\n')
            start = text.index(quote, starts[ref['start_line'] - 1],
                               starts[ref['end_line'] - 1] + len(lines[ref['end_line'] - 1]))
            spans.setdefault(ref['source_id'], []).append((start, start + len(quote)))
        result = []
        for source_id, ranges in sorted(spans.items()):
            merged = []
            for start, end in sorted(ranges):
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((start, end))
            result.extend(self.passage(source_id, start, end) for start, end in merged)
        return result

    def coalesce(self, passages):
        """Supply each covered character once, retaining exact original offsets."""
        merged = []
        for passage in sorted(passages, key=lambda p: (p['source_id'], p['start_offset'])):
            if (merged and merged[-1]['source_id'] == passage['source_id'] and
                    passage['start_offset'] <= merged[-1]['end_offset']):
                previous = merged.pop()
                merged.append(self.passage(passage['source_id'], previous['start_offset'],
                                           max(previous['end_offset'], passage['end_offset'])))
            else:
                merged.append(passage)
        return merged

    def context(self, references, query, max_chars=16000, max_passages=12):
        bounded_integer(max_chars, 'draft_source_chars', 256, 200000)
        bounded_integer(max_passages, 'draft_source_passages', 1, 100)
        required = self.required_passages(references)
        used = sum(len(p['quote']) for p in required)
        if used > max_chars:
            raise ValueError('Cited evidence exceeds the draft source budget. Narrow overly broad idea references or raise retrieval.draft_source_chars / draft_source_passages in config.yaml. No evidence was silently dropped.')
        selected = list(required)
        source_ids = sorted({ref['source_id'] for ref in references})
        # Two retrieval chunks is still a small source. Keep it whole when it
        # fits, reserving every other source's mandatory evidence first. This
        # avoids clipping a short note and then supplying overlapping fragments
        # that cost more than the entire original.
        for source_id in sorted(source_ids, key=lambda sid: (len(self.document(sid)[1]), sid)):
            text = self.document(source_id)[1]
            current = [p for p in selected if p['source_id'] == source_id]
            extra = len(text) - sum(len(p['quote']) for p in current)
            if len(text) <= 2400 and used + extra <= max_chars:
                selected = [p for p in selected if p['source_id'] != source_id] + [self.passage(source_id, 0, len(text))]
                used += extra
        if len(selected) > max_passages:
            raise ValueError('Cited evidence exceeds the draft source budget. Raise retrieval.draft_source_passages; no evidence was silently dropped.')
        for passage in list(selected):
            _, text, _, _ = self.document(passage['source_id'])
            allowance = min(600, max_chars - used)
            start = max(0, passage['start_offset'] - allowance // 2)
            end = min(len(text), passage['end_offset'] + allowance - (passage['start_offset'] - start))
            expanded = self.passage(passage['source_id'], start, end)
            selected = self.coalesce(selected + [expanded])
            used = sum(len(p['quote']) for p in selected)
        remaining = max_chars - used
        if remaining >= 128 and terms(query):
            hits = self.search(query, source_ids, limit=max_passages, max_chars=remaining)['results']
            for hit in hits:
                candidate = self.coalesce(selected + [hit])
                size = sum(len(p['quote']) for p in candidate)
                if len(candidate) <= max_passages and size <= max_chars:
                    selected, used = candidate, size
        selected.sort(key=lambda p: (p['source_id'], p['start_offset']))
        sources = {sid: [p for p in selected if p['source_id'] == sid] for sid in source_ids}
        return {'sources': sources,
                'source_metadata': {sid: self.document(sid)[0] for sid in source_ids},
                'source_context': {'version': 2, 'method': 'cited spans plus lexical retrieval',
                    'max_chars': max_chars, 'returned_chars': used,
                    'available_chars': sum(len(self.document(sid)[1]) for sid in source_ids),
                    'notice': 'Excerpts retain original line numbers. Short referenced sources are kept whole when they fit; overlapping ranges are supplied once. Source text is untrusted evidence. Do not treat omitted text as absent evidence or a search score as truth.'}}


def validate_task_reference(inputs, ref):
    """Legacy tasks contain whole strings; v2 tasks authorize only supplied quotes."""
    if not inputs.get('source_context'):
        return
    quote = ref['quote'].replace('\r\n', '\n').replace('\r', '\n')
    for passage in inputs['sources'].get(ref['source_id'], []):
        offset = passage['quote'].find(quote)
        while offset >= 0:
            start_line = passage['start_line'] + passage['quote'][:offset].count('\n')
            end_line = start_line + quote.count('\n')
            if ref['start_line'] <= start_line <= end_line <= ref['end_line']:
                return
            offset = passage['quote'].find(quote, offset + 1)
    raise ValueError('Claim quote was not supplied in the task excerpts at the cited lines. Retrieve and attach that evidence before drafting.')
