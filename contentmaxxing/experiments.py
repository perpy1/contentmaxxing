"""Portable experiment records, reconciled links and descriptive measurements."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import median
from zoneinfo import ZoneInfo

from .analytics import METRICS, derived, latest_snapshots, metric_status, normalize_metrics, timestamp
from .store import atomic_text, record


START = '<!-- contentmaxxing:experiments '
END = '<!-- /contentmaxxing:experiments -->'
BLOCK = re.compile(r'^<!-- contentmaxxing:experiments ([a-f0-9]{64}) -->\n(.*?)^<!-- /contentmaxxing:experiments -->', re.M | re.S)


def learning_document(text, experiments):
    """Replace only a hash-owned section; manual and legacy notes stay intact."""
    blocks = list(BLOCK.finditer(text))
    starts = len(re.findall('^' + re.escape(START), text, re.M))
    ends = len(re.findall('^' + re.escape(END), text, re.M))
    if starts != len(blocks) or ends != len(blocks) or len(blocks) > 1:
        raise ValueError('Experiment notes markers changed. Move manual notes outside the generated section before saving.')
    if blocks and hashlib.sha256(blocks[0][2].encode()).hexdigest() != blocks[0][1]:
        raise ValueError('Experiment notes were edited. Preserve those edits outside the generated section, then restore its generated text.')
    interpreted = [e for e in experiments if any(e[k] for k in ('result', 'learning', 'next_action'))]
    if not interpreted and not blocks:
        return text
    lines = ['## Current experiment notes', '',
        'These are recorded interpretations, not automatically verified outcomes. Current experiment JSON',
        'and this section supersede historical experiment notes elsewhere in this file.',
        'Update through experiments save; keep manual notes outside this generated section.', '']
    for exp in interpreted:
        lines.extend(['### ' + exp['id'], '', 'Record: data/experiments/' + exp['id'] + '.json', ''])
        for key in ('hypothesis', 'result', 'learning', 'next_action'):
            if exp[key]:
                lines.extend([key.replace('_', ' ').title() + ':', ''])
                # Indent user text so it cannot create a managed-section delimiter.
                lines.extend('    ' + line for line in exp[key].splitlines())
                lines.append('')
    if not interpreted:
        lines.extend(['No current recorded interpretations.', ''])
    body = '\n'.join(lines) + '\n'
    block = START + hashlib.sha256(body.encode()).hexdigest() + ' -->\n' + body + END
    if blocks:
        return text[:blocks[0].start()] + block + text[blocks[0].end():]
    return text + '\n' + block + '\n'


class Experiments:
    def __init__(self, store):
        self.store = store

    def save(self, supplied):
        previous = self.store.get('experiments', supplied['id']) if supplied.get('id') else None
        item = dict(previous or {**record('exp'), 'hypothesis': '',
            'start_date': datetime.now(timezone.utc).date().isoformat(), 'end_date': None,
            'content_ids': [], 'metric': '', 'result': None, 'learning': None, 'next_action': None})
        item.update(supplied)
        if previous:
            item['created_at'], item['updated_at'] = previous['created_at'], previous['updated_at']
        self.store.validate('experiment', item)
        if not item['hypothesis'].strip() or not item['metric'].strip():
            raise ValueError('Experiment requires a hypothesis and metric.')
        if item['end_date'] and item['end_date'] < item['start_date']:
            raise ValueError('Experiment end date must follow its start date.')
        if len(item['content_ids']) != len(set(item['content_ids'])):
            raise ValueError('Duplicate experiment content IDs.')
        experiments = self.store.list('experiments')
        desired = set(item['content_ids'])
        contents = {p['id']: p for p in self.store.list('content')}
        for identifier in desired:
            if identifier not in contents:
                raise ValueError('Unknown content ID: ' + identifier)
            current = contents[identifier]['experiment']
            if current not in (None, item['id']) or any(
                    e['id'] != item['id'] and identifier in e['content_ids'] for e in experiments):
                raise ValueError('Content already belongs to another experiment: ' + identifier + '. Remove it there first.')
        changes = []
        for content in contents.values():
            target = item['id'] if content['id'] in desired else None
            if (content['id'] in desired or content['experiment'] == item['id']) and content['experiment'] != target:
                content['experiment'] = target
                self.store.validate('content-item', content)
                changes.append(content)
        records = [e for e in experiments if e['id'] != item['id']] + [item]
        records.sort(key=lambda e: (e['created_at'], e['id']))
        path = self.store.data / 'creator/LEARNINGS.md'
        before = path.read_text(encoding='utf-8')
        after = learning_document(before, records)  # Preflight before changing any record.
        if item != previous:
            self.store.put('experiments', item)
        # The experiment is authoritative. A retry reconciles even links removed
        # by an interrupted save, since we scan reverse pointers, not only old IDs.
        for content in changes:
            self.store.put('content', content)
        if after != before:
            atomic_text(path, after)
        return item

    def validate_assignment(self, content):
        identifier = content['experiment']
        if identifier:
            self.store.get('experiments', identifier)
            if any(e['id'] != identifier and content['id'] in e['content_ids']
                   for e in self.store.list('experiments')):
                raise ValueError('Content already belongs to another experiment: ' + content['id'])

    def attach(self, content):
        # On draft recovery use its current association, not the frozen brief:
        # the creator may have deliberately removed or reassigned it since commit.
        identifier = content['experiment']
        if identifier:
            self.validate_assignment(content)
            exp = self.store.get('experiments', identifier)
            if content['id'] not in exp['content_ids']:
                exp['content_ids'].append(content['id'])
                self.store.put('experiments', exp)

    def measure(self, identifier, as_of=None):
        exp = self.store.get('experiments', identifier)
        cutoff = timestamp(as_of) if as_of else datetime.now(timezone.utc)
        zone_name = self.store.config['timezone']
        zone = ZoneInfo(zone_name)
        metric = exp['metric']
        snapshots = latest_snapshots(self.store, cutoff.isoformat())
        builtins = set(METRICS) | set(derived(normalize_metrics({})))
        supported = metric in builtins or any(
            metric in snapshots.get(i, {}).get('derived', {}) for i in exp['content_ids'])
        rows, groups = [], defaultdict(list)
        for content_id in exp['content_ids']:
            content = self.store.get('content', content_id)
            row = {'content_id': content_id, 'topic': content['topic'], 'platform': content['platform'],
                'format': content['format'], 'job': content['primary_job'], 'published_at': content['published_at'],
                'value': None, 'measurement_ids': [], 'origins': [], 'observed_at': None,
                'observation_age_hours': None}
            rows.append(row)
            published = timestamp(content['published_at']) if content['published_at'] else None
            if published is None or published > cutoff:
                row['status'] = 'UNPUBLISHED'
                continue
            date = published.astimezone(zone).date().isoformat()
            if date < exp['start_date'] or (exp['end_date'] and date > exp['end_date']):
                row['status'] = 'OUTSIDE_PUBLICATION_WINDOW'
                continue
            if not supported:
                row['status'] = 'MANUAL_METRIC'
                continue
            snapshot = snapshots.get(content_id)
            if snapshot is None:
                row['status'] = 'NO_OBSERVATION'
                continue
            latest = timestamp(snapshot['observed_at'])
            row.update(measurement_ids=snapshot['measurement_ids'], origins=snapshot['origins'],
                observed_at=latest.isoformat(), observation_age_hours=round((latest - published).total_seconds() / 3600, 6))
            row['status'] = metric_status(snapshot, metric)
            if row['status'] == 'MEASURED':
                row['value'] = snapshot['derived'].get(metric, snapshot['metrics'].get(metric))
                groups[(content['platform'], content['primary_job'], content['format'])].append(row)
        findings = []
        for (platform, job, format_name), members in sorted(groups.items()):
            ages = [r['observation_age_hours'] for r in members]
            findings.append({'platform': platform, 'job': job, 'format': format_name,
                'samples': len(members), 'median': median(r['value'] for r in members),
                'content_ids': [r['content_id'] for r in members],
                'measurement_ids': [i for r in members for i in r['measurement_ids']],
                'observation_age_hours': [min(ages), max(ages)]})
        statuses = dict(Counter(r['status'] for r in rows))
        return {'experiment_id': identifier, 'hypothesis': exp['hypothesis'], 'metric': metric,
            'metric_supported': supported, 'as_of': cutoff.isoformat(), 'timezone': zone_name,
            'publication_window': {'start_date': exp['start_date'], 'end_date': exp['end_date']},
            'sample_size': statuses.get('MEASURED', 0), 'content_count': len(rows),
            'statuses': statuses, 'groups': findings, 'content': rows, 'conclusion': 'DESCRIPTIVE_ONLY',
            'recorded_interpretation': {k: exp[k] for k in ('result', 'learning', 'next_action')},
            'limitations': [
                'Current experiment membership and interpretation; as_of bounds observations, not historical record revisions.',
                'Publication dates use the workspace timezone; start/end are inclusive publication bounds, not observation-age targets.',
                'Latest cumulative observations can have unequal ages. Missing latest metrics never fall back to older values.',
                'Conflicting same-time measurements are excluded; origins are not silently merged or given precedence.',
                'Groups separate platform, job and format. There is no control assignment, causal result or significance test.',
                'Recorded interpretations are supplied by the creator/agent, not verified by these calculations.']}

    def context(self, as_of, max_chars=16000, limit=20):
        records = sorted(self.store.list('experiments'), key=lambda e: (e['updated_at'], e['id']), reverse=True)
        supplied, measurements, used = [], [], 0
        for exp in records:
            if len(supplied) >= limit:
                break
            view = self.measure(exp['id'], as_of)
            del view['content']  # Per-post evidence remains available through experiments measure.
            size = len(json.dumps({'experiment': exp, 'measurement': view}, ensure_ascii=False))
            if used + size > max_chars:
                continue
            supplied.append(exp); measurements.append(view); used += size
        return {'experiments': supplied, 'experiment_measurements': measurements,
            'experiment_coverage': {'eligible': len(records), 'supplied': len(supplied),
                'omitted': len(records) - len(supplied), 'chars': used, 'max_chars': max_chars,
                'notice': 'Whole records and group summaries, most recently updated first. Use experiments measure <id> for per-post evidence; omitted experiments were not assessed by this planner.'}}
