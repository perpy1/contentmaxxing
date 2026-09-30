"""Shared workflow. Providers supply intelligence; connectors supply transport."""
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional

from jsonschema import Draft202012Validator

from .analytics import (METRICS, ALIASES, derived, group_findings, latest_snapshots,
                        normalize_metrics, posting_windows, score, timestamp, winners)
from .providers import PendingTask, provider_from
from .feedback import Feedback
from .retrieval import SourceLibrary, validate_task_reference
from .store import PACKAGE, Store, atomic_json, atomic_text, normalize, now, record
from .revisions import Revisions, editable, fingerprint


def mutation(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        with self.store.lock():
            return method(self, *args, **kwargs)
    return run


MINE_CONTRACT = {'type': 'object', 'additionalProperties': False, 'required': ['ideas'], 'properties': {
    'ideas': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
        'required': ['topic', 'quote', 'start_line', 'end_line', 'category'], 'properties': {
            'topic': {'type': 'string', 'minLength': 1}, 'quote': {'type': 'string', 'minLength': 1},
            'start_line': {'type': 'integer', 'minimum': 1}, 'end_line': {'type': 'integer', 'minimum': 1},
            'category': {'type': 'string'}, 'content_pillar': {'type': ['string', 'null']},
            'proof': {'type': 'array', 'items': {'type': 'string'}},
            'priority': {'type': 'integer', 'minimum': 0, 'maximum': 100},
            'article_candidate': {'type': 'boolean'}, 'notes': {'type': 'string'},
            'existing_idea_id': {'type': 'string', 'pattern': '^idea_[a-f0-9]{12}$'}}}}}}
DRAFT_CONTRACT = {'type': 'object', 'additionalProperties': False,
    'required': ['body', 'title', 'claims', 'quality_notes', 'framework'], 'properties': {
        'body': {'type': 'string', 'minLength': 1}, 'title': {'type': 'string'},
        'claims': {'type': 'array', 'items': {'type': 'object', 'required': ['claim', 'source_reference'],
            'additionalProperties': False, 'properties': {'claim': {'type': 'string'}, 'source_reference': {
                'type': 'object', 'additionalProperties': False, 'required': ['source_id', 'start_line', 'end_line', 'quote'],
                'properties': {'source_id': {'type': 'string'}, 'start_line': {'type': 'integer', 'minimum': 1},
                               'end_line': {'type': 'integer', 'minimum': 1}, 'quote': {'type': 'string', 'minLength': 1}}}}}},
        'quality_notes': {'type': 'array', 'items': {'type': 'string'}},
        'framework': {'type': ['string', 'null']}}}
FRAMEWORKS = {'HADES', 'BUZZ', 'LOGAN', 'JUAN', 'EP', 'FREDERICK', 'SERIES / TECHNICAL OPERATOR'}
TRANSITIONS = {'NEEDS_REVIEW': {'APPROVED', 'ARCHIVED'},
               'APPROVED': {'NEEDS_REVIEW', 'SCHEDULED', 'PUBLISHED', 'ARCHIVED'},
               'SCHEDULED': {'PUBLISHED'}, 'PUBLISHED': {'COMPOUND', 'ARCHIVED'},
               'COMPOUND': {'ARCHIVED'}, 'ARCHIVED': set()}


class Engine:
    def __init__(self, workspace, provider=None, provider_name=None):
        self.store = Store(workspace)
        self.provider = provider
        self.provider_name = provider_name

    def get_provider(self):
        return self.provider or provider_from(self.store.config, self.provider_name)

    def profile_template(self):
        schema = json.loads((self.store.assets / 'schemas/creator-profile.schema.json').read_text())
        return {k: {} if v.get('type') == 'object' else [] if v.get('type') == 'array' else ''
                for k, v in schema['properties'].items()}

    @mutation
    def onboard(self, supplied):
        path = self.store.data / 'creator/profile.json'
        if path.exists():
            raise ValueError('Creator already onboarded. Edit documents deliberately; onboarding does not overwrite identity.')
        profile = self.profile_template()
        profile.update(supplied)
        self.store.validate('creator-profile', profile)
        default_roles = {'x': 'Discovery, opinions, conversation and written depth',
                         'linkedin': 'Business context, authority and professional proof',
                         'tiktok': 'Discovery, personality, demonstrations and visual systems',
                         'substack': 'Depth, owned audience, guides and long-term trust'}
        for platform in profile['platforms']:
            if platform in default_roles:
                profile['platform_roles'].setdefault(platform, default_roles[platform])
        self.store.validate('creator-profile', profile)
        def sections(title, fields):
            result = '# ' + title + '\n'
            for key in fields:
                result += '\n## ' + key.replace('_', ' ').title() + '\n\n'
                value = profile[key]
                result += (json.dumps(value, ensure_ascii=False, indent=2) if value else 'Unknown — collect creator evidence.') + '\n'
            return result
        docs = {
            'BRAND_BRAIN.md': sections('Brand Brain', ['name', 'category', 'niche', 'audience', 'ideal_customer',
                'promise', 'enemy', 'beliefs', 'differentiator', 'expertise', 'career_history', 'proof_results',
                'stories', 'strong_opinions', 'content_pillars', 'supporting_topics', 'ownership_topics',
                'excluded_topics', 'platform_roles', 'business_goals', 'content_goals', 'restrictions']),
            'VOICE.md': sections('Voice', ['desired_tone', 'writing_samples', 'top_posts', 'articles_newsletters']) +
                '\n## Onboarding evidence snapshot\n\n' + ('Samples supplied at onboarding; analyze them with the voice skill. No default casing or personality is imposed.\n'
                if profile['writing_samples'] else 'No writing samples at onboarding. Voice remains provisional until actual evidence is analyzed; gather feedback on initial drafts.\n'),
            'CONTENT_PILLARS.md': sections('Content Pillars', ['content_pillars', 'ownership_topics', 'supporting_topics',
                'excluded_topics', 'platforms', 'posting_cadence', 'platform_roles']),
            'OFFER.md': sections('Offer', ['what_they_sell', 'ideal_customer', 'cta_offer', 'business_goals', 'restrictions'])}
        for name, text in docs.items():
            doc = self.store.data / 'creator' / name
            if not doc.exists():
                atomic_text(doc, text)
        # The profile is the onboarding completion marker. Write it last so a
        # failed document write can be retried without stranding a partial brain.
        atomic_json(path, profile)
        return profile

    @mutation
    def capture(self, path, kind='transcript', consent='unspecified', notes=''):
        self.store.brain()
        path = Path(path)
        try:
            text = path.read_bytes().decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('Text sources only in v1; transcribe/OCR binary media before capture.') from None
        if not text.strip():
            raise ValueError('Source is empty.')
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        existing = next((x for x in self.store.list('sources') if x['sha256'] == digest), None)
        if existing:
            return existing
        source = {**record('src'), 'title': path.name, 'kind': kind, 'sha256': digest,
                  'consent': consent, 'notes': notes}
        source['path'] = 'data/sources/' + source['id'] + '.txt'
        atomic_text(self.store.root / source['path'], text)
        return self.store.put('sources', source)

    def task(self, operation, skill, inputs, contract):
        instructions = (self.store.assets / 'prompts/system.md').read_text() + '\n' + (
            self.store.assets / ('skills/' + skill + '/SKILL.md')).read_text() + '\n' + (
            self.store.assets / 'prompts/quality-checks.md').read_text()
        if operation == 'mine':
            instructions += ('\nIf inputs.existing_ideas contains the same actual topic, set existing_idea_id '
                'to its supplied ID and copy its topic exactly to attach current-source evidence to it. '
                'Keep independent angles separate. Existing titles/notes are retrieval guidance, not proof; quote '
                'only the supplied source/window. Attachment preserves the existing idea metadata; '
                'your full extraction response is retained on the completed task.\n')
        if operation == 'draft' and inputs['platform'] in ('x_article', 'substack'):
            instructions += '\n' + (self.store.assets / 'skills/article-writing/SKILL.md').read_text()
            instructions += '\n' + (self.store.assets / 'templates/article-frameworks.md').read_text()
        if operation == 'draft' and inputs.get('parent_content'):
            instructions += '\n' + (self.store.assets / 'skills/compound/SKILL.md').read_text()
        if operation == 'draft':
            instructions += ('\nTask context: sources maps each source ID to exact excerpts with original '
                'line numbers, not a complete transcript. Cite only quotes supplied in those excerpts. '
                'Keep speakers and uncertainty intact; nearby text can qualify a claim. '
                'creator_feedback contains explicit scoped creator direction. Apply it where relevant; '
                'examples are style preferences, not factual evidence. Flag conflicting instructions '
                'in quality_notes instead of silently choosing one. Feedback does not authorize publication.\n')
            if inputs.get('editorial_brief'):
                instructions += ('\neditorial_brief defines this piece\'s angle, reader payoff and selection reason. '
                    'Deliver that specific utility in the creator\'s voice. The brief is direction, not proof: '
                    'verify factual claims against source excerpts and flag missing evidence in quality_notes.\n')
            if inputs.get('revision_target'):
                path = self.store.assets / 'skills/content-revision/SKILL.md'
                instructions += '\n' + (path if path.exists() else PACKAGE / 'skills/content-revision/SKILL.md').read_text()
        return {**record('task'), 'operation': operation, 'skill': skill, 'status': 'PENDING',
                'provider': self.provider_name or self.store.config['provider'], 'inputs': inputs,
                'instructions': instructions, 'output_contract': contract, 'result_ids': [], 'error': None}

    def execute(self, task):
        self.store.put('tasks', task)
        provider = self.provider or provider_from(self.store.config, task['provider'])
        try:
            output = (provider.extract(task) if task['operation'] == 'mine' else
                      provider.analyze(task) if task['operation'] in ('plan', 'compound', 'voice') else provider.generate(task))
            return self.complete_task(task['id'], output)
        except PendingTask:
            raise
        except Exception as exc:
            # Completion may already have persisted its stable result ID. Keep
            # that checkpoint instead of overwriting it with this stale object.
            task = self.store.get('tasks', task['id'])
            task['error'] = str(exc)
            self.store.put('tasks', task)
            raise

    @mutation
    def mine(self, source_id, restart=False, retry=False):
        from .mining import Mining, existing_idea_context, latest, settings
        text = self.store.source_text(source_id)
        run = latest(self.store, source_id)
        if run or len(text) > settings(self.store)['chunk_chars']:
            # Preserve legacy pending whole-source work rather than orphaning it.
            legacy = next((t for t in self.store.list('tasks') if t['operation'] == 'mine' and
                t['inputs']['source_id'] == source_id and t['status'] == 'PENDING' and
                'source_window' not in t['inputs']), None)
            if legacy:
                raise PendingTask(legacy['id'])
            return Mining(self).run(source_id, restart=restart, retry=retry)
        # Repeated calls reuse the pending task; completed tasks remain deliberately retryable/deduplicated.
        pending = next((t for t in self.store.list('tasks') if t['status'] == 'PENDING' and
                        t['operation'] == 'mine' and t['inputs']['source_id'] == source_id), None)
        if pending:
            raise PendingTask(pending['id'])
        source = self.store.get('sources', source_id)
        task = self.task('mine', 'transcript-mining', {'source_id': source_id, 'source': source,
            'text': text, 'creator': self.store.brain(),
            **existing_idea_context(self.store, source_id, text, settings(self.store)['idea_context_chars'])}, MINE_CONTRACT)
        return self.execute(task)

    def idea_from(self, candidate, source_id, mode, parent=None, addition=None):
        ref = {'source_id': source_id, 'quote': candidate['quote'],
               'start_line': candidate['start_line'], 'end_line': candidate['end_line']}
        self.store.validate_reference(ref)
        topic = candidate['topic'].strip()
        return {**record('idea'), 'topic': topic, 'category': candidate['category'],
                'source': source_id, 'source_reference': [ref], 'content_pillar': candidate.get('content_pillar'),
                'content_type': None, 'format': None, 'primary_job': 'Reach', 'best_platform': 'x',
                'priority': candidate.get('priority', 50), 'status': 'BACKLOG', 'proof': candidate.get('proof', []),
                'notes': candidate.get('notes', ''), 'used_date': None, 'published_urls': [], 'performance': {},
                'follow_up_angle': topic if parent else None, 'article_candidate': candidate.get('article_candidate', False),
                'experiment': None, 'parent_content_id': parent, 'addition': addition,
                'dedupe_key': hashlib.sha256(normalize(topic).encode()).hexdigest(), 'extraction_mode': mode}

    def persist_idea(self, idea):
        def same_topic(existing):
            if existing['dedupe_key'] == idea['dedupe_key']:
                return True
            a, b = normalize(existing['topic']), normalize(idea['topic'])
            negators = {'no', 'not', 'never', 'without', 'avoid'}
            if set(a.split()) & negators != set(b.split()) & negators:
                return False
            same_span = any(r == s for r in existing['source_reference'] for s in idea['source_reference'])
            return same_span and SequenceMatcher(None, a, b).ratio() >= .92
        duplicate = next((i for i in self.store.list('ideas') if same_topic(i)), None)
        if duplicate:
            for ref in idea['source_reference']:
                if ref not in duplicate['source_reference']:
                    duplicate['source_reference'].append(ref)
            return self.store.put('ideas', duplicate)
        return self.store.put('ideas', idea)

    @mutation
    def select(self, idea_id, platform='x', format_name=None, job=None):
        idea = self.store.get('ideas', idea_id)
        if idea['status'] == 'ARCHIVED':
            raise ValueError('Archived idea cannot be selected.')
        formats = self.store.registry['platforms'].get(platform)
        if not formats:
            raise ValueError('Unsupported platform: ' + platform)
        chosen = format_name or ('short post' if platform == 'x' else formats[0])
        if chosen not in formats:
            raise ValueError('Format is not registered for platform: ' + chosen)
        if job and job not in self.store.registry['jobs']:
            raise ValueError('Unknown job: ' + job)
        idea.update({'status': 'SELECTED', 'format': chosen, 'best_platform': platform,
                     'primary_job': job or idea['primary_job']})
        return self.store.put('ideas', idea)

    @mutation
    def cite_idea(self, idea_id, source_id, start_line, end_line, quote):
        idea = self.store.get('ideas', idea_id)
        ref = {'source_id': source_id, 'start_line': start_line, 'end_line': end_line, 'quote': quote}
        self.store.validate_reference(ref)
        if ref in idea['source_reference']:
            return idea
        if any(t['status'] == 'PENDING' and t['operation'] == 'draft' and
               t['inputs']['idea']['id'] == idea_id for t in self.store.list('tasks')):
            raise ValueError('A draft task already snapshots this idea. Use tasks cite to add evidence to that pending task, or attach evidence before the next draft.')
        idea['source_reference'].append(ref)
        return self.store.put('ideas', idea)

    @mutation
    def resolve_idea(self, idea_id, resolutions):
        from .compounding import Compounding
        return Compounding(self).resolve(idea_id, resolutions)

    @mutation
    def cancel_task(self, task_id, reason):
        if self.store.get('tasks', task_id)['operation'] == 'voice':
            from .voice import Voice
            return Voice(self).cancel(task_id, reason)
        if self.store.get('tasks', task_id)['operation'] == 'compound':
            from .compounding import Compounding
            return Compounding(self).cancel(task_id, reason)
        return Revisions(self.store).cancel(task_id, reason)

    @mutation
    def cite_task(self, task_id, source_id, start_line, end_line, quote):
        task = self.store.get('tasks', task_id)
        if task['operation'] == 'compound':
            from .compounding import Compounding
            return Compounding(self).cite(task, {'source_id': source_id, 'start_line': start_line,
                                                 'end_line': end_line, 'quote': quote})
        if task['operation'] != 'draft' or task['status'] != 'PENDING' or task.get('planned_result_id') or Revisions(self.store).prepared(task):
            raise ValueError('Only an uncommitted pending draft task can receive more evidence.')
        ref = {'source_id': source_id, 'start_line': start_line, 'end_line': end_line, 'quote': quote}
        self.store.validate_reference(ref)
        extras = list(task['inputs'].get('extra_source_reference', []))
        refs = task['inputs']['idea']['source_reference']
        if ref in refs or ref in extras:
            return task
        extras.append(ref)
        retrieval = self.store.config.get('retrieval', {})
        evidence = SourceLibrary(self.store).context(refs + extras, task['inputs']['idea']['topic'],
            retrieval.get('draft_source_chars', 16000), retrieval.get('draft_source_passages', 12))
        task['inputs'].update(evidence)
        task['inputs']['extra_source_reference'] = extras
        return self.store.put('tasks', task)

    @mutation
    def refresh_feedback(self, task_id):
        task = self.store.get('tasks', task_id)
        if task['operation'] != 'draft' or task['status'] != 'PENDING' or task.get('planned_result_id') or Revisions(self.store).prepared(task):
            raise ValueError('Only an uncommitted pending draft task can refresh feedback.')
        task['inputs']['creator_feedback'] = Feedback(self.store).context(task['inputs']['platform'],
            task['inputs'].get('revision_target', {}).get('id'))
        return self.store.put('tasks', task)

    @mutation
    def draft(self, idea_id, platform=None, editorial_report=None, editorial_brief=None):
        idea = self.store.get('ideas', idea_id)
        if idea['status'] in ('BACKLOG', 'ARCHIVED'):
            raise ValueError('Select the idea with a platform, format and job first.')
        platform = platform or idea['best_platform']
        if idea['format'] not in self.store.registry['platforms'].get(platform, []):
            raise ValueError('Select a native format for this platform first.')
        pending = next((t for t in self.store.list('tasks') if t['status'] == 'PENDING' and
                        t['operation'] == 'draft' and t['inputs']['idea']['id'] == idea_id and
                        not t['inputs'].get('revision_target') and
                        t['inputs']['platform'] == platform), None)
        if pending:
            saved = pending['inputs']['idea']
            if (saved['format'], saved['primary_job']) != (idea['format'], idea['primary_job']):
                raise ValueError('Pending draft has a different format/job. Complete it before changing its selection.')
            if editorial_brief is not None and pending['inputs'].get('editorial_brief') != editorial_brief:
                raise ValueError('Pending draft has a different editorial brief. Complete it before executing this plan.')
            raise PendingTask(pending['id'])
        task = self.draft_task(idea, platform, editorial_report, editorial_brief=editorial_brief)
        idea['status'] = 'DRAFTING'
        self.store.put('ideas', idea)
        return self.execute(task)

    def draft_task(self, idea, platform, editorial_report=None, revision_target=None, direction='', editorial_brief=None):
        from .editorial import validate_brief
        from .compounding import require_ready
        require_ready(idea)
        validate_brief(self.store, editorial_brief, idea, platform)
        refs = idea['source_reference']
        for ref in refs:
            self.store.validate_reference(ref)
        skill = {'x': 'x-writing', 'x_article': 'article-writing', 'linkedin': 'linkedin',
                 'tiktok': 'tiktok', 'substack': 'substack', 'substack_note': 'substack'}.get(platform)
        if not skill:
            raise ValueError('New platform needs an engine skill route; see README extension guide.')
        parent_context = None
        if idea['parent_content_id']:
            parent = self.store.get('content', idea['parent_content_id'])
            parent_context = {key: parent[key] for key in
                              ('id', 'topic', 'body', 'platform', 'format', 'primary_job', 'source_reference')}
        retrieval = self.store.config.get('retrieval', {})
        evidence = SourceLibrary(self.store).context(refs, idea['topic'],
            retrieval.get('draft_source_chars', 16000), retrieval.get('draft_source_passages', 12))
        inputs = {'idea': idea, 'platform': platform, 'creator': self.store.brain(),
            'parent_content': parent_context,
            **evidence, 'creator_feedback': Feedback(self.store).context(platform,
                revision_target['id'] if revision_target else None),
            'editorial_report': editorial_report,
            'editorial_brief': editorial_brief,
            'article_words': self.store.config['article_words'], 'x_max_chars': self.store.config['x_max_chars']}
        if revision_target:
            inputs.update(revision_target=revision_target, revision_direction=direction)
        return self.task('draft', skill, inputs, DRAFT_CONTRACT)

    @mutation
    def revise(self, content_id, direction=''):
        content = self.store.get('content', content_id)
        editable(content)
        pending = next((t for t in self.store.list('tasks') if t['status'] == 'PENDING' and
            t['inputs'].get('revision_target', {}).get('id') == content_id), None)
        if pending:
            if Revisions(self.store).prepared(pending):
                return Revisions(self.store).apply_task(pending)
            if fingerprint(pending['inputs']['revision_target']) != fingerprint(content):
                raise ValueError('Draft changed while the revision was pending. Cancel that task and revise the current draft.')
            if direction and direction != pending['inputs']['revision_direction']:
                raise ValueError('A revision is already pending with different direction. Complete or cancel it before starting another.')
            raise PendingTask(pending['id'])
        feedback = Feedback(self.store).context(content['platform'], content_id)
        if not direction.strip() and not feedback:
            raise ValueError('Supply revision direction or record explicit creator feedback first.')
        idea = self.store.get('ideas', content['idea_id'])
        refs = list(content['source_reference'])
        for claim in content['claims']:
            if claim['source_reference'] not in refs:
                refs.append(claim['source_reference'])
        idea.update(topic=content['topic'], format=content['format'], primary_job=content['primary_job'],
                    best_platform=content['platform'], source_reference=refs, experiment=content['experiment'])
        task = self.draft_task(idea, content['platform'], revision_target=content, direction=direction.strip())
        return self.execute(task)

    @mutation
    def complete_task(self, task_id, output):
        task = self.store.get('tasks', task_id)
        if task['status'] == 'CANCELLED':
            raise ValueError('Task was cancelled. Start a new task from current evidence.')
        if task['status'] == 'COMPLETED':
            if task['operation'] == 'voice':
                from .voice import Voice
                return [Voice(self).get(identifier) for identifier in task['result_ids']]
            if task['operation'] == 'plan':
                from .planning import Planning
                return [Planning(self).get(identifier) for identifier in task['result_ids']]
            return [self.store.get('ideas' if task['operation'] in ('mine', 'compound') else 'content', i) for i in task['result_ids']]
        if task['operation'] == 'voice':
            from .voice import Voice
            return [Voice(self).complete(task, output)]
        if task['operation'] == 'compound':
            from .compounding import Compounding
            return Compounding(self).complete(task, output)
        if task['operation'] == 'plan':
            from .editorial import Editorial
            return [Editorial(self).complete(task, output)]
        if task['inputs'].get('revision_target') and Revisions(self.store).prepared(task):
            return Revisions(self.store).apply_task(task)
        if task['operation'] == 'draft' and task.get('planned_result_id'):
            path = self.store.path('content', task['planned_result_id'])
            if path.exists():
                # The content write committed before the task checkpoint. Its
                # current revision, including any creator edits, is authoritative.
                item = self.store.get('content', task['planned_result_id'])
                if item['idea_id'] != task['inputs']['idea']['id'] or item['platform'] != task['inputs']['platform']:
                    raise ValueError('Saved draft result does not match its task.')
                self.store.put('content', item)  # Also restores a missing Markdown sidecar.
                self.link_editorial_experiment(task, item)
                current = self.store.get('ideas', item['idea_id'])
                current['status'] = item['status']
                self.store.put('ideas', current)
                task.update(status='COMPLETED', result_ids=[item['id']], error=None)
                self.store.put('tasks', task)
                return [item]
        Draft202012Validator(task['output_contract']).validate(output)
        mode = task['provider']
        if task['operation'] == 'mine':
            from .mining import existing_target, validate_window
            for candidate in output['ideas']:
                validate_window(task['inputs'], candidate)
            targets = [existing_target(self.store, task['inputs'], candidate) for candidate in output['ideas']]
            prepared = [self.idea_from(c, task['inputs']['source_id'], mode) for c in output['ideas']]
            # Validate the entire response before any record is persisted.
            for idea in prepared:
                self.store.validate('idea', idea)
            results = [self.cite_idea(target, idea['source'], idea['source_reference'][0]['start_line'],
                                    idea['source_reference'][0]['end_line'], idea['source_reference'][0]['quote'])
                       if target else self.persist_idea(idea) for target, idea in zip(targets, prepared)]
            task['extraction_output'] = output
        elif task['operation'] == 'draft':
            idea = task['inputs']['idea']
            platform = task['inputs']['platform']
            from .compounding import require_ready
            require_ready(idea)
            from .editorial import validate_brief
            validate_brief(self.store, task['inputs'].get('editorial_brief'), idea, platform)
            if platform in ('x_article', 'substack') and output['framework'] not in FRAMEWORKS:
                raise ValueError('An article must choose exactly one registered framework.')
            if platform not in ('x_article', 'substack') and output['framework'] is not None:
                raise ValueError('Framework applies only to an article.')
            if platform == 'x' and idea['format'] not in ('long-form X post', 'Reddit-style breakdown') and len(output['body']) > task['inputs']['x_max_chars']:
                raise ValueError('Short X draft exceeds configured character limit; select a long format explicitly.')
            if idea['parent_content_id']:
                parent = self.store.get('content', idea['parent_content_id'])
                resemblance = SequenceMatcher(None, normalize(parent['body']), normalize(output['body'])).ratio()
                if resemblance >= .9:
                    raise ValueError('Compound draft repeats its parent. Add new utility, context, proof, story, argument or format with a native expression.')
            allowed_sources = set(task['inputs']['sources'])
            for claim in output['claims']:
                ref = claim['source_reference']
                if ref['source_id'] not in allowed_sources:
                    raise ValueError('Claim cites a source not supplied to the task.')
                self.store.validate_reference(ref)
                validate_task_reference(task['inputs'], ref)
            references = idea['source_reference'] + task['inputs'].get('extra_source_reference', [])
            for ref in references:
                self.store.validate_reference(ref)
            notes = list(output['quality_notes'])
            if not output['claims']:
                notes.append('No claim map supplied: review each factual claim against the cited sources.')
            if not json.loads((self.store.data / 'creator/profile.json').read_text())['writing_samples']:
                notes.append('Creator writing samples are missing; voice is not yet learned.')
            item = {**record('post'), 'idea_id': idea['id'], 'topic': idea['topic'], 'platform': platform,
                'format': idea['format'], 'primary_job': idea['primary_job'], 'status': 'NEEDS_REVIEW',
                'body': output['body'].strip(), 'title': output['title'], 'source_reference': references,
                'claims': output['claims'], 'quality_notes': notes, 'generation_mode': mode,
                'framework': output['framework'], 'approved_at': None, 'scheduled_at': None,
                'published_at': None, 'published_urls': [], 'remote': {},
                'experiment': (task['inputs'].get('editorial_brief') or {}).get('experiment_id') or idea['experiment'], 'revision': 1}
            self.store.validate('content-item', item)
            if task['inputs'].get('revision_target'):
                return Revisions(self.store).apply_task(task, item)
            # Store a stable planned result ID before writing, enabling crash-retry without duplicate content.
            if task.get('planned_result_id'):
                item['id'] = task['planned_result_id']
            from .experiments import Experiments
            Experiments(self.store).validate_assignment(item)
            if not task.get('planned_result_id'):
                task['planned_result_id'] = item['id']
                self.store.put('tasks', task)
            results = [self.store.put('content', item)]
            self.link_editorial_experiment(task, item)
            current = self.store.get('ideas', idea['id'])
            current['status'] = 'NEEDS_REVIEW'
            self.store.put('ideas', current)
        else:
            raise ValueError('Unsupported task operation.')
        task.update({'status': 'COMPLETED', 'result_ids': list(dict.fromkeys(x['id'] for x in results)), 'error': None})
        self.store.put('tasks', task)
        return results

    def link_editorial_experiment(self, task, item):
        from .experiments import Experiments
        Experiments(self.store).attach(item)

    @mutation
    def edit(self, content_id, body):
        content = self.store.get('content', content_id)
        if content['status'] not in ('NEEDS_REVIEW', 'APPROVED'):
            raise ValueError('Only local unscheduled drafts can be edited. Capture a new version of published content.')
        if content['remote']:
            raise ValueError('Remote draft exists; edit it through the connector preserving comments, then reconcile locally.')
        after = {**content, 'body': body, 'status': 'NEEDS_REVIEW', 'approved_at': None,
                 'claims': [], 'revision': content['revision'] + 1,
                 'quality_notes': content['quality_notes'] + ['Edited draft: evidence and voice review required again.']}
        return Revisions(self.store).manual(content, after)

    @mutation
    def transition(self, content_id, status, url=None, published_at=None, scheduled_at=None):
        content = self.store.get('content', content_id)
        if status not in TRANSITIONS[content['status']]:
            raise ValueError('Invalid content transition: ' + content['status'] + ' → ' + status)
        if status == 'APPROVED':
            for ref in content['source_reference']:
                self.store.validate_reference(ref)
            content['approved_at'] = now()
        if status == 'SCHEDULED':
            if not scheduled_at:
                raise ValueError('Scheduling requires an explicit timezone-aware timestamp.')
            timestamp(scheduled_at)
            content['scheduled_at'] = scheduled_at
        if status == 'PUBLISHED':
            if not url or not url.startswith(('https://', 'http://')):
                raise ValueError('Recording publication requires the real published URL.')
            content['published_urls'] = list(dict.fromkeys(content['published_urls'] + [url]))
            content['published_at'] = published_at or now()
            timestamp(content['published_at'])
        content['status'] = status
        self.store.put('content', content)
        idea = self.store.get('ideas', content['idea_id'])
        idea['status'] = status
        if status == 'PUBLISHED':
            idea['used_date'] = content['published_at']
            idea['published_urls'] = list(dict.fromkeys(idea['published_urls'] + content['published_urls']))
        self.store.put('ideas', idea)
        return content

    def prepare_measurement(self, content_id, values, observed_at, origin):
        content = self.store.get('content', content_id)
        if content['status'] not in ('PUBLISHED', 'COMPOUND', 'ARCHIVED') or not content['published_at']:
            raise ValueError('Analytics require recorded publication, not an unreviewed draft.')
        observed = timestamp(observed_at)
        if observed < timestamp(content['published_at']):
            raise ValueError('Analytics observation predates publication.')
        metrics = normalize_metrics(values)
        item = {**record('metric'), 'content_id': content_id, 'platform': content['platform'],
                'observed_at': observed_at, 'metrics': metrics, 'derived': derived(metrics), 'origin': origin}
        self.store.validate('analytics', item)
        return item

    def persist_measurement(self, item):
        existing = [x for x in self.store.list('analytics') if x['content_id'] == item['content_id'] and
                    timestamp(x['observed_at']) == timestamp(item['observed_at']) and x['origin'] == item['origin']]
        if existing:
            # Equivalent timezone spellings describe the same origin/instant.
            # Repair any legacy duplicates consistently while retaining their IDs.
            saved = []
            for old in existing:
                candidate = {**item, **{k: old[k] for k in ('id', 'created_at', 'updated_at', 'observed_at')}}
                saved.append(self.store.put('analytics', candidate) if candidate != old else old)
            item = saved[0]
        else:
            self.store.put('analytics', item)
        content = self.store.get('content', item['content_id'])
        idea = self.store.get('ideas', content['idea_id'])
        # Import order must not become performance order. The cache is a view of
        # current observations; original records are the authority for as-of reads.
        latest = latest_snapshots(self.store).get(content['id'])
        if latest is not None and idea['performance'].get(content['id']) != latest:
            idea['performance'][content['id']] = latest
            self.store.put('ideas', idea)
        elif latest is None and content['id'] in idea['performance']:
            del idea['performance'][content['id']]
            self.store.put('ideas', idea)
        return item

    @mutation
    def import_csv(self, path):
        with Path(path).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            columns = set(reader.fieldnames or [])
            if not {'content_id', 'observed_at'} <= columns:
                raise ValueError('CSV requires content_id and observed_at columns.')
            unknown = columns - {'content_id', 'observed_at'} - set(METRICS) - set(ALIASES)
            if unknown:
                raise ValueError('Unknown CSV columns: ' + ', '.join(sorted(unknown)))
            prepared = []
            for index, row in enumerate(reader, 2):
                try:
                    prepared.append(self.prepare_measurement(row['content_id'],
                        {k: v for k, v in row.items() if k not in ('content_id', 'observed_at')},
                        row['observed_at'], 'csv'))
                except Exception as exc:
                    raise ValueError('CSV row %s: %s' % (index, exc)) from None
        return [self.persist_measurement(item) for item in prepared]

    @mutation
    def manual_metrics(self, content_id, values, observed_at=None):
        return self.persist_measurement(self.prepare_measurement(content_id, values, observed_at or now(), 'manual'))

    @mutation
    def report(self, end_date=None, timezone_name=None):
        from zoneinfo import ZoneInfo
        zone_name = timezone_name or self.store.config['timezone']
        zone = ZoneInfo(zone_name)
        end = timestamp(end_date) if end_date else datetime.now(zone)
        start = end - timedelta(days=7)
        latest = latest_snapshots(self.store, end.isoformat())
        contents = [c for c in self.store.list('content') if c['published_at'] and
                    start <= timestamp(c['published_at']) <= end and c['id'] in latest]
        ranked = sorted([(c, score(c, latest[c['id']], self.store.registry)) for c in contents],
                        key=lambda pair: (pair[1] is not None, pair[1] or 0), reverse=True)
        window_ids = {c['id'] for c in contents}
        winner_ids = [w['content_id'] for w in winners(self.store, end.isoformat()) if w['content_id'] in window_ids]
        # Rank within platform/job rather than compare unlike metric scales.
        groups = {}
        for c, value in ranked:
            if value is not None:
                groups.setdefault((c['platform'], c['primary_job']), []).append(c['id'])
        top = [ids[0] for ids in groups.values()]
        weak = [ids[-1] for ids in groups.values() if len(ids) >= 3]
        growth = {'attributed_new_followers': None, 'attributed_net_followers': None,
                  'account_follower_change': None}
        for metric, key in [('new_followers', 'attributed_new_followers'), ('net_followers', 'attributed_net_followers')]:
            values = [latest[c['id']]['metrics'][metric] for c in contents]
            if values and all(v is not None for v in values):
                growth[key] = sum(values)
        article_candidates = [i['id'] for i in self.store.list('ideas') if i['article_candidate'] and i['status'] != 'ARCHIVED']
        report = {**record('report'), 'start_date': start.isoformat(), 'end_date': end.isoformat(),
            'timezone': zone_name, 'sample_size': len(contents), 'growth': growth,
            'top_posts': top, 'weak_posts': weak,
            'winning_topics': group_findings(contents, latest, self.store.registry, ['topic']),
            'winning_formats': group_findings(contents, latest, self.store.registry, ['format']),
            'winning_jobs': group_findings(contents, latest, self.store.registry, []),
            'combinations': group_findings(contents, latest, self.store.registry, ['topic', 'format']),
            'posting_windows': posting_windows(contents, latest, self.store.registry, zone_name),
            'compound': winner_ids, 'stop': [],
            'test': ['Test one source-backed topic/format/job combination; use a matched cohort and a fixed observation window.'],
            'article_candidates': article_candidates,
            'editorial_brief': 'Mine real evidence first. Use measured winners for new-value angles; keep native platform voice. Source shortages override batch targets.',
            'limitations': ['Findings are tentative; cumulative metrics may have unequal observation ages.',
                'Peer baselines use published history with known job metrics, not causal experiments.',
                'Trust, Proof and Authority require manually interpreted evidence; impressions are not substitutes.',
                'Missing account or per-post follower attribution stays unknown. Weak posts do not imply a strategy to stop.']}
        conflicts = [c['id'] for c in contents if any(latest[c['id']]['conflicts'].values())]
        if conflicts:
            report['limitations'].append('%s posts have conflicting latest values; those values are excluded. Inspect original records with analytics show <content-id> --as-of %s. First affected IDs: %s' %
                (len(conflicts), end.isoformat(), ', '.join(conflicts[:20])))
        followers_dir = self.store.data / 'analytics/raw'
        series = sorted(followers_dir.glob('followers_*.json')) if followers_dir.exists() else []
        if series:
            raw = json.loads(series[-1].read_text())
            points = [p for p in raw.get('data', []) if start.date().isoformat() <= p['date'] <= end.date().isoformat()]
            if len(points) >= 2:
                growth['account_follower_change'] = points[-1]['followers_count'] - points[0]['followers_count']
        self.store.put('reports', report)
        atomic_text(self.store.data / 'reports' / (report['id'] + '.md'),
                    '# Weekly editorial report\n\n' + report['editorial_brief'] + '\n\n```json\n' + json.dumps(report, indent=2) + '\n```\n')
        return report

    @mutation
    def compound(self, content_id, fresh=False, query='', as_of=None):
        from .compounding import Compounding
        if (self.provider_name or self.store.config['provider']) == 'extractive':
            if fresh or query:
                raise ValueError('A new compound analysis or retrieval query needs external or openai-compatible mode.')
            return self._compound_extractive(content_id, as_of)
        return Compounding(self).request(content_id, fresh, query, as_of)

    def _compound_extractive(self, content_id, as_of=None):
        winner = next((w for w in winners(self.store, as_of) if w['content_id'] == content_id), None)
        if not winner:
            raise ValueError('Not a measured winner: need a known job metric, sufficient matched peers and meaningful lift.')
        content = self.store.get('content', content_id)
        existing = [i for i in self.store.list('ideas') if i['parent_content_id'] == content_id]
        if existing:
            return existing
        quote = content['source_reference'][0]
        moves = [
            ('What to check before applying: ' + content['topic'], 'utility', 'checklist', 'Bookmarks / Saves',
             'Build a usable checklist from the original source; capture any missing steps.'),
            ('Where this stops working: ' + content['topic'], 'argument', 'contrarian take', 'Conversation',
             'Capture a real counterexample or scope limit before writing this angle.'),
            ('Working-notes guide: ' + content['topic'], 'format', 'X article', 'Authority',
             'Expand with sourced explanation and actionable sections; do not pad or copy the original.')]
        prepared = []
        for topic, addition, format_name, job, note in moves:
            candidate = {'topic': topic, 'category': 'compound opportunity', 'quote': quote['quote'],
                'start_line': quote['start_line'], 'end_line': quote['end_line'], 'notes': note,
                'article_candidate': format_name == 'X article', 'priority': 80}
            idea = self.idea_from(candidate, quote['source_id'], 'extractive compound heuristic; development required', content_id, addition)
            idea.update({'format': format_name, 'primary_job': job,
                         'best_platform': 'x_article' if format_name == 'X article' else 'x',
                         'performance': {'parent': winner}})
            if addition == 'format' and format_name == content['format']:
                # Already an article: a new format alone is impossible. Offer new utility instead.
                idea.update({'addition': 'utility', 'notes': 'Add a reusable implementation worksheet with new utility, sourced steps required.'})
            prepared.append(idea)
        results = [self.persist_idea(i) for i in prepared]
        if content['status'] == 'PUBLISHED':
            self.transition(content_id, 'COMPOUND')
        learning_path = self.store.data / 'creator/LEARNINGS.md'
        atomic_text(learning_path, learning_path.read_text() + '\n- %s: %s performed %.2fx matched median (%s, %s peers). Tentative; test new-value angles.\n' %
                    (content_id, content['topic'], winner['lift'], winner['metric'], winner['peers']))
        return results

    @mutation
    def experiment(self, supplied):
        from .experiments import Experiments
        return Experiments(self.store).save(supplied)

    def measure_experiment(self, identifier, as_of=None):
        from .experiments import Experiments
        return Experiments(self.store).measure(identifier, as_of)
