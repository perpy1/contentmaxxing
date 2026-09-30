"""Job-aware metrics. Unknown denominators and missing measurements stay null."""
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
import math
from zoneinfo import ZoneInfo

METRICS = ['impressions', 'views', 'engagements', 'engagement_rate', 'likes', 'replies',
           'reposts', 'shares', 'bookmarks', 'profile_visits', 'new_followers', 'unfollows',
           'net_followers', 'link_clicks', 'leads', 'calls']
ALIASES = {'comments': 'replies', 'saves': 'bookmarks', 'profile_clicks': 'profile_visits',
           'follows': 'new_followers'}


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamps must include a timezone offset.')
    return result


def ratio(numerator, denominator, scale=1):
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * scale, 6)


def normalize_metrics(values):
    unknown = set(values) - set(METRICS) - set(ALIASES)
    if unknown:
        raise ValueError('Unknown metric columns: ' + ', '.join(sorted(unknown)))
    result = {k: None for k in METRICS}
    seen = set()
    for key, value in values.items():
        key = ALIASES.get(key, key)
        if key in seen:
            raise ValueError('Duplicate metric/alias columns: ' + key)
        seen.add(key)
        if value is not None and value != '':
            if isinstance(value, bool):
                raise ValueError('Metric must be numeric, not boolean: ' + key)
            number = float(value)
            if not math.isfinite(number):
                raise ValueError('Metric must be finite: ' + key)
            if number < 0 and key != 'net_followers':
                raise ValueError('Negative count: ' + key)
            result[key] = number
    if result['net_followers'] is None and result['new_followers'] is not None and result['unfollows'] is not None:
        result['net_followers'] = result['new_followers'] - result['unfollows']
    return result


def derived(metrics):
    impressions = metrics['impressions']
    result = {k + '_per_1k': ratio(metrics[k], impressions, 1000)
              for k in ['profile_visits', 'bookmarks', 'leads', 'calls']}
    result.update({'follows_per_1k': ratio(metrics['new_followers'], impressions, 1000),
                   'share_rate': ratio(metrics['shares'], impressions),
                   'save_rate': ratio(metrics['bookmarks'], impressions),
                   'profile_to_follow_conversion': ratio(metrics['new_followers'], metrics['profile_visits']),
                   'follow_rate': ratio(metrics['new_followers'], impressions),
                   'reply_rate': ratio(metrics['replies'], impressions),
                   'engagement_rate': ratio(metrics['engagements'], impressions)})
    return result


def latest_snapshots(store, as_of=None):
    """Resolve the latest instant without choosing an arbitrary import origin.

    Returned views are not analytics records. Each raw and derived value must
    agree across all records at that instant; derived rates are calculated within
    each original observation, never from counts merged across records.
    """
    latest, observations = {}, defaultdict(list)
    cutoff = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    contents = {c['id']: c for c in store.list('content')}
    for item in store.list('analytics'):
        observed = timestamp(item['observed_at'])
        content = contents.get(item['content_id'])
        if (not content or not content['published_at'] or item['platform'] != content['platform'] or
                not timestamp(content['published_at']) <= observed <= cutoff):
            continue
        identifier = item['content_id']
        if identifier not in latest or observed > latest[identifier]:
            latest[identifier], observations[identifier] = observed, [item]
        elif observed == latest[identifier]:
            observations[identifier].append(item)
    result = {}
    for identifier, items in observations.items():
        items.sort(key=lambda i: i['id'])
        view = {'content_id': identifier, 'platform': contents[identifier]['platform'],
                'observed_at': latest[identifier].astimezone(timezone.utc).isoformat(),
                'measurement_ids': [i['id'] for i in items], 'origins': [i['origin'] for i in items],
                'metrics': {}, 'derived': {}, 'conflicts': {'metrics': [], 'derived': []}}
        for category, values in [('metrics', [i['metrics'] for i in items]),
                                 ('derived', [{**i['derived'], **derived(i['metrics'])} for i in items])]:
            for name in sorted({key for value in values for key in value}):
                agrees = all(value.get(name) == values[0].get(name) for value in values)
                view[category][name] = values[0].get(name) if agrees else None
                if not agrees:
                    view['conflicts'][category].append(name)
        result[identifier] = view
    return result


def metric_status(snapshot, metric):
    if snapshot is None:
        return 'NO_OBSERVATION'
    category = 'derived' if metric in snapshot['derived'] else 'metrics'
    if metric in snapshot.get('conflicts', {}).get(category, []):
        return 'CONFLICTING_OBSERVATIONS'
    if metric not in snapshot[category]:
        return 'MANUAL_METRIC'
    return 'MEASURED' if snapshot[category][metric] is not None else 'METRIC_MISSING'


def inspect_measurement(store, content_id, as_of=None):
    content = store.get('content', content_id)
    cutoff = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    snapshot = latest_snapshots(store, cutoff.isoformat()).get(content_id)
    metric = store.registry['job_metrics'].get(content['primary_job'])
    return {'content_id': content_id, 'platform': content['platform'], 'job': content['primary_job'],
            'as_of': cutoff.isoformat(), 'job_metric': metric, 'job_score': score(content, snapshot, store.registry) if snapshot else None,
            'metric_status': metric_status(snapshot, metric), 'snapshot': snapshot,
            'observations': [store.get('analytics', i) for i in snapshot['measurement_ids']] if snapshot else [],
            'notice': 'Latest cumulative observation at or before the cutoff. Conflicting values are unknown; no older-value fallback, cross-origin count merging or causal claim.'}


def score(content, analytics, registry):
    metric = registry['job_metrics'].get(content['primary_job'])
    if metric is None:
        return None
    return analytics['derived'].get(metric, analytics['metrics'].get(metric))


def winners(store, as_of=None):
    latest = latest_snapshots(store, as_of)
    config = store.config['winner']
    groups = defaultdict(list)
    for content in store.list('content'):
        measurement = latest.get(content['id'])
        if content['status'] not in ('PUBLISHED', 'COMPOUND') or measurement is None:
            continue
        impressions = measurement['metrics']['impressions']
        value = score(content, measurement, store.registry)
        if value is not None and impressions is not None and impressions >= config['minimum_impressions']:
            groups[(content['platform'], content['primary_job'])].append((content, value))
    result = []
    for key, candidates in groups.items():
        for content, value in candidates:
            peers = [v for c, v in candidates if c['id'] != content['id']]
            if len(peers) < config['minimum_peers']:
                continue
            baseline = median(peers)
            # Zero baseline is not enough evidence for an infinite "lift" claim.
            if baseline > 0 and value >= baseline * config['multiplier']:
                result.append({'content_id': content['id'], 'score': value, 'baseline': baseline,
                               'lift': round(value / baseline, 3), 'peers': len(peers),
                               'metric': store.registry['job_metrics'][key[1]],
                               'measurement_ids': latest[content['id']]['measurement_ids']})
    return sorted(result, key=lambda item: item['lift'], reverse=True)


def group_findings(contents, latest, registry, fields):
    groups = defaultdict(list)
    for item in contents:
        if item['id'] in latest:
            value = score(item, latest[item['id']], registry)
            if value is not None:
                # Keep platform/job in the key so incompatible objectives are never pooled.
                key = tuple(item[field] for field in fields) + (item['platform'], item['primary_job'])
                groups[key].append(value)
    return [{'dimensions': dict(zip(list(fields) + ['platform', 'primary_job'], key)),
             'samples': len(values), 'median_job_score': median(values),
             'confidence': 'tentative'} for key, values in groups.items()]


def posting_windows(contents, latest, registry, timezone_name):
    zone = ZoneInfo(timezone_name)
    groups = defaultdict(list)
    for content in contents:
        if content['published_at'] and content['id'] in latest:
            value = score(content, latest[content['id']], registry)
            if value is not None:
                local = timestamp(content['published_at']).astimezone(zone)
                groups[(content['platform'], content['primary_job'], local.strftime('%A'), local.hour)].append(value)
    return [{'platform': key[0], 'job': key[1], 'day': key[2], 'hour': key[3],
             'samples': len(values), 'median_job_score': median(values),
             'confidence': 'tentative'} for key, values in groups.items()]
