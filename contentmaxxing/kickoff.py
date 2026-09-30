"""Resumable creator launch. The conversational agent supplies judgment and results."""
import json
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml

from .providers import PendingTask
from .mining import MiningIncomplete, source_progress
from .intake import Intake
from .welcome import CHOICES
from .store import PACKAGE, atomic_json, atomic_text, now


class Kickoff:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store
        self.path = self.store.data / 'creator/kickoff.json'

    def save(self, state):
        state['updated_at'] = now()
        atomic_json(self.path, state)

    def task_for(self, operation, identifier, platform=None):
        tasks = [t for t in self.store.list('tasks') if t['operation'] == operation and
                 not t['inputs'].get('revision_target') and
                 (t['inputs']['source_id'] == identifier if operation == 'mine' else
                  t['inputs']['idea']['id'] == identifier and t['inputs']['platform'] == platform)]
        return tasks[-1] if tasks else None

    def reply(self, state, phase, message, questions=None, task_ids=None, candidates=None):
        state['phase'] = phase
        self.save(state)
        tasks = [self.store.get('tasks', i) for i in task_ids or []]
        return {'workspace': str(self.store.root), 'phase': phase, 'message': message,
                'questions': questions or [], 'focus_platform': state['platform'],
                'target_drafts': state['batch_size'], 'source_ids': state['source_ids'],
                'mining_progress': [source_progress(self.store, sid) for sid in state['source_ids']],
                'intake_mode': state.get('intake_mode'),
                'choices': CHOICES if phase == 'WELCOME' else [],
                'welcome_image': str(self.store.assets / 'assets/welcome.png'),
                'intake': Intake(self.store).summary(),
                'profile_proposal': state.get('profile_proposal'),
                'candidate_ideas': candidates or [], 'content_ids': state['content_ids'],
                'pending_tasks': [{'id': t['id'], 'file': str(self.store.path('tasks', t['id'])),
                                   'skill': t['skill'], 'error': t['error']} for t in tasks],
                'agent_guide': str(self.store.assets / 'skills/kickoff/SKILL.md'),
                'agent_action': {
                    'WELCOME': 'Show the welcome HUD and offer curated interview or mega file dump. Save their choice with start --mode interview|files.',
                    'FILE_DROP': 'Invite a folder or multiple source files. Save supported files using start --mode files --source <path>; report unsupported files honestly.',
                    'SOURCE_REVIEW': 'Use the kickoff file-dump instructions to inspect preserved documents in manageable batches. Propose only supported creator facts with file/line evidence using start --profile-proposal <json>. Do not ask the user to prepare JSON.',
                    'PROFILE_REVIEW': 'Show the proposed creator profile, cited evidence, unknowns and conflicts. Ask the creator to confirm/correct. Only then use start --confirm-profile, with --answers for their corrections.',
                    'CONTEXT': 'Ask only the unanswered questions in normal conversation. Save supplied facts and resume start.',
                    'SOURCE': 'Ask for real work and voice samples. A short interview is valid source material; preserve exact answers.',
                    'MINING': 'Execute the pending extraction contracts yourself, import their results, and call start again. Do not delegate task-file work to the creator.',
                    'CHOOSE_TOPICS': 'Use editorial-planning to choose sourced ideas and native format + job. Select with the CLI, then call start with --idea for each choice.',
                    'DRAFTING': 'Execute the pending writing contracts yourself, import their results, and call start again. Present the completed drafts to the creator.',
                    'REVIEW': 'Show the actual drafts, explain their topics/jobs and ask for voice/fact edits. Show LAUNCH_PLAN.md and the next capture step. Publication still needs explicit approval.'
                }[phase]}

    def run(self, answers=None, sources=None, batch_size=None, platform=None, idea_ids=None, timezone_name='UTC',
            mode=None, profile_proposal=None, confirm_profile=False):
        if mode not in (None, 'interview', 'files'):
            raise ValueError('Choose interview or files for intake mode.')
        if not (self.store.root / 'config.yaml').exists():
            self.store.init(provider=self.engine.provider_name or 'external', timezone_name=timezone_name)
        with self.store.lock():
            # Add the new launch entrypoint to older workspaces without replacing customized skills.
            skill_path = self.store.assets / 'skills/kickoff'
            if not skill_path.exists():
                shutil.copytree(PACKAGE / 'skills/kickoff', skill_path)
            if not (self.store.root / 'START_HERE.md').exists():
                shutil.copy2(PACKAGE / 'START_HERE.md', self.store.root / 'START_HERE.md')
            returning = self.path.exists()
            state = json.loads(self.path.read_text()) if returning else {
                'version': 2, 'created_at': now(), 'updated_at': now(), 'phase': 'WELCOME',
                'profile_draft': {}, 'pending_sources': [], 'source_ids': [],
                'intake_mode': None,
                'batch_size': 3, 'platform': None, 'selections': [], 'content_ids': [],
                'workflow_configured': False}
            profile_path = self.store.data / 'creator/profile.json'
            existing_profile = json.loads(profile_path.read_text()) if profile_path.exists() else None
            # Old launches keep their existing conversation; new blank launches offer a choice.
            state.setdefault('intake_mode', 'interview' if returning else None)
            if mode:
                state['intake_mode'] = mode
            elif not state['intake_mode']:
                if answers or existing_profile:
                    state['intake_mode'] = 'interview'
                elif sources:
                    state['intake_mode'] = 'files'
            if batch_size is not None:
                if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
                    raise ValueError('Starter batch size must be a positive integer.')
                if state['selections'] and batch_size != state['batch_size']:
                    raise ValueError('The starter batch is already selected. Finish it, then plan another batch.')
                state['batch_size'] = batch_size
            if platform:
                if platform not in self.store.registry['platforms']:
                    raise ValueError('Unknown platform: ' + platform)
                if state['selections'] and platform != state['platform']:
                    raise ValueError('The starter batch already has a platform. Finish it before planning another.')
                state['platform'] = platform
            if answers is not None:
                schema = json.loads((self.store.assets / 'schemas/creator-profile.schema.json').read_text())
                schema['required'] = []
                Draft202012Validator(schema).validate(answers)
                if existing_profile:
                    changed = [key for key, value in answers.items() if existing_profile.get(key) != value]
                    if changed:
                        raise ValueError('Creator already onboarded; update the creator documents/profile deliberately for: ' + ', '.join(changed))
                else:
                    state['profile_draft'].update(answers)
            intake = Intake(self.store)
            if state['intake_mode'] == 'files' and not intake.summary()['documents'] and state['pending_sources']:
                # Adopt preserved files from launches created before the bulk-intake manifest.
                legacy_paths = []
                for relative in state['pending_sources']:
                    queued = (self.store.root / relative).resolve()
                    if (self.store.data / 'inbox').resolve() not in queued.parents:
                        raise ValueError('Queued source is outside the workspace inbox.')
                    legacy_paths.append(queued)
                intake.ingest(legacy_paths)
            if sources:
                before = {e['sha256'] for e in intake.summary()['documents']}
                imported = intake.ingest(sources)
                if before != {e['sha256'] for e in imported['documents']} and not state.get('file_profile_reviewed'):
                    state.pop('profile_proposal', None)
            # Reconcile the durable inventory after an interrupted copy/checkpoint.
            for document in intake.summary()['documents']:
                relative = document['path']
                if relative not in state['pending_sources'] and relative not in state.get('processed_sources', []):
                    state['pending_sources'].append(relative)
            if profile_proposal is not None:
                if existing_profile or state['intake_mode'] != 'files' or state.get('file_profile_reviewed'):
                    raise ValueError('Profile proposals are for the initial file-dump setup. Refine existing identity deliberately.')
                state['profile_proposal'] = intake.validate_proposal(profile_proposal)
            if confirm_profile:
                if not state.get('profile_proposal') or existing_profile:
                    raise ValueError('A proposed profile is required before confirmation.')
                intake.validate_proposal(state['profile_proposal'])
                # Direct creator answers/corrections outrank suggestions derived from source files.
                state['profile_draft'] = {**state['profile_proposal']['profile'], **state['profile_draft']}
                state['file_profile_reviewed'] = True
            self.save(state)
            if not state['intake_mode']:
                return self.reply(state, 'WELCOME', 'CONTENTMAXXING — Capture → Create → Compound.', [
                    'How would you like to start: 1. Curated interview, or 2. Mega file dump?'])
            if state['intake_mode'] == 'files' and not existing_profile and not state.get('file_profile_reviewed'):
                if not intake.summary()['documents']:
                    return self.reply(state, 'FILE_DROP', 'Drop your source material and I’ll organize it into a starting point.', [
                        'Share a folder or multiple files: transcripts, notes, old posts, articles, and profile material.'])
                if not state.get('profile_proposal'):
                    return self.reply(state, 'SOURCE_REVIEW', 'Your files are preserved. I’ll read them before asking you to repeat what they already explain.')
                return self.reply(state, 'PROFILE_REVIEW', 'Here’s the profile your material supports. Let’s check that it represents you.', [
                    'What should I correct in this proposed profile, and which unanswered details would you like to add?'])
            profile = existing_profile or state['profile_draft']
            questions = []
            if not existing_profile:
                if not profile.get('name') or not profile.get('audience'):
                    questions.append('What should I call you, what do you do, and who do you want your content to help?')
                if not profile.get('content_goals'):
                    questions.append('What should content do for you over the next few months—and is there anything you sell?')
                if not profile.get('platforms'):
                    questions.append('Where do you want to start posting? If you know your pace, how many posts per week feels sustainable?')
            if questions:
                return self.reply(state, 'CONTEXT', 'Let’s build your content engine around your work and the people you want to reach.', questions)
            platforms = profile.get('platforms', [])
            if not state['platform']:
                if not platforms:
                    return self.reply(state, 'CONTEXT', 'Choose one starting platform.', ['Where do you want to start posting?'])
                state['platform'] = {'substack': 'substack_note'}.get(platforms[0], platforms[0])
            if state['platform'] not in self.store.registry['platforms']:
                raise ValueError('Choose a supported starting platform with --platform.')
            selected_parent = {'x_article': 'x', 'substack_note': 'substack'}.get(state['platform'], state['platform'])
            if platforms and selected_parent not in platforms and state['platform'] not in platforms:
                raise ValueError('Starting platform must be one the creator selected during onboarding.')
            if not state['pending_sources'] and not self.store.list('sources'):
                source_questions = ['Share a recent call, project, working note, customer question, mistake or win. If you have no files, tell me what happened, what you did and what changed.']
                if not profile.get('writing_samples'):
                    source_questions.append('Share a few posts or paragraphs that sound like you, if you have them.')
                if not profile.get('restrictions'):
                    source_questions.append('What topics, details or claims should stay out of your content?')
                return self.reply(state, 'SOURCE', 'We have a direction. Let’s find useful material in work you’ve already done.', source_questions)
            created_profile = existing_profile is None
            if created_profile:
                state['owns_profile'] = True
                self.save(state)
                profile = self.engine.onboard(state['profile_draft'])
            for relative in list(state['pending_sources']):
                source_path = (self.store.root / relative).resolve()
                if self.store.data / 'inbox' not in source_path.parents:
                    raise ValueError('Queued source is outside the workspace inbox.')
                source = self.engine.capture(source_path, kind='kickoff material', notes='Supplied during creator kickoff; preserve speaker attribution.')
                if source['id'] not in state['source_ids']:
                    state['source_ids'].append(source['id'])
                state['pending_sources'].remove(relative)
                if relative not in state.setdefault('processed_sources', []):
                    state['processed_sources'].append(relative)
                self.save(state)
            if not state['source_ids']:
                state['source_ids'] = [s['id'] for s in self.store.list('sources')]
            if not state['workflow_configured']:
                if state.get('owns_profile'):
                    self.configure_first_week(profile, state)
                # Existing creators retain their cadence and workflow edits.
                state['workflow_configured'] = True
                self.save(state)
            if state['content_ids']:
                self.launch_plan(state, profile)
                return self.reply(state, 'REVIEW', 'Your first batch and launch plan are ready for review.')
            pending, unfinished_mining = [], False
            for source_id in state['source_ids']:
                state_of_source = source_progress(self.store, source_id)
                if state_of_source['status'] != 'COMPLETED':
                    try:
                        self.engine.mine(source_id)
                    except (PendingTask, MiningIncomplete):
                        pass
                    except ValueError:
                        saved = source_progress(self.store, source_id)
                        if not any(self.store.get('tasks', tid).get('error') for tid in saved['pending_task_ids']):
                            raise
                    state_of_source = source_progress(self.store, source_id)
                pending.extend(state_of_source['pending_task_ids'])
                unfinished_mining |= state_of_source['status'] != 'COMPLETED'
            if unfinished_mining:
                return self.reply(state, 'MINING', 'I’m finding distinct topics, stories and useful details in your source material.', task_ids=pending)
            used = {c['idea_id'] for c in self.store.list('content') if c['platform'] == state['platform']}
            candidates = [i for i in self.store.list('ideas') if i['status'] != 'ARCHIVED' and
                          any(r['source_id'] in state['source_ids'] for r in i['source_reference']) and
                          i['id'] not in used]
            candidates.sort(key=lambda i: (-i['priority'], i['created_at']))
            if idea_ids and not state['selections']:
                chosen = list(dict.fromkeys(idea_ids))
                if len(chosen) > state['batch_size']:
                    raise ValueError('Choose no more ideas than the starter batch target.')
                if set(chosen) - {i['id'] for i in candidates}:
                    raise ValueError('Choose unused, non-archived ideas from the captured source material.')
                state['selections'] = [{'idea_id': i, 'task_id': None} for i in chosen]
                self.save(state)
            elif idea_ids and list(dict.fromkeys(idea_ids)) != [s['idea_id'] for s in state['selections']]:
                raise ValueError('Starter ideas are already selected. Resume without changing their IDs.')
            if not state['selections']:
                if not candidates:
                    return self.reply(state, 'SOURCE', 'This material has no unused candidates for the starting platform. Capture another real example.', [
                        'What recent decision, customer question or piece of work could we turn into something useful?'])
                return self.reply(state, 'CHOOSE_TOPICS', 'The idea bank is ready. I’ll choose the strongest topics for a small first batch.',
                    candidates=[{k: i[k] for k in ['id', 'topic', 'category', 'priority', 'proof', 'notes', 'source_reference', 'format', 'primary_job']} for i in candidates])
            pending, content_ids = [], []
            for slot in state['selections']:
                task = self.store.get('tasks', slot['task_id']) if slot['task_id'] else self.task_for('draft', slot['idea_id'], state['platform'])
                if task is None:
                    idea = self.store.get('ideas', slot['idea_id'])
                    native_format = idea['format'] if idea['format'] in self.store.registry['platforms'][state['platform']] else None
                    self.engine.select(idea['id'], state['platform'], native_format, idea['primary_job'])
                    try:
                        self.engine.draft(idea['id'], state['platform'])
                    except PendingTask:
                        pass
                    except ValueError:
                        if self.task_for('draft', idea['id'], state['platform']) is None:
                            raise
                    task = self.task_for('draft', idea['id'], state['platform'])
                slot['task_id'] = task['id']
                self.save(state)
                if task['status'] == 'COMPLETED':
                    content_ids.extend(task['result_ids'])
                else:
                    pending.append(task['id'])
            if pending:
                return self.reply(state, 'DRAFTING', 'I’m turning the selected topics into drafts in your voice.', task_ids=pending)
            state['content_ids'] = list(dict.fromkeys(content_ids))
            self.launch_plan(state, profile)
            return self.reply(state, 'REVIEW', 'Your first batch and launch plan are ready for review.')

    def configure_first_week(self, profile, state):
        path = self.store.root / 'workflows.yaml'
        config = yaml.safe_load(path.read_text())
        counts = {platform: 0 for platform in config['counts']}
        cadence = profile.get('posting_cadence', {})
        for platform, count in cadence.items():
            platform = {'substack': 'substack_note'}.get(platform, platform)
            if platform in counts and ({'x_article': 'x', 'substack_note': 'substack'}.get(platform, platform) in profile['platforms']):
                counts[platform] = count
        if not cadence:
            counts[state['platform']] = state['batch_size']
        config['counts'] = counts
        atomic_text(path, yaml.safe_dump(config, sort_keys=False))

    def launch_plan(self, state, profile):
        config = yaml.safe_load((self.store.root / 'workflows.yaml').read_text())
        lines = ['# Your content engine', '', 'Capture → Create → Compound', '',
                 'Audience: ' + (profile.get('audience') or 'To clarify with the creator.'),
                 'Goal: ' + '; '.join(profile.get('content_goals', [])),
                 'Starting platform: ' + state['platform'], '', '## First batch', '']
        for content_id in state['content_ids']:
            content = self.store.get('content', content_id)
            lines.append('- [%s](../content/%s.md) — %s · %s · %s' %
                         (content['topic'], content_id, content['format'], content['primary_job'], content['status']))
        shortfall = max(0, state['batch_size'] - len(state['content_ids']))
        if shortfall:
            lines += ['', 'Source quality limited this batch: %s of %s target drafts. Capture more evidence before expanding it.' %
                      (len(state['content_ids']), state['batch_size'])]
        lines += ['', '## First-week rhythm', '',
                  ('Weekly targets from your setup: ' if profile.get('posting_cadence') else 'Proposed weekly targets, adjustable after review: ') +
                  ', '.join('%s: %s' % (p, n) for p, n in config['counts'].items() if n),
                  '', '1. Review the drafts for voice, facts and useful detail. Approval is per post.',
                  '2. Capture one new real question, decision, workflow or result as it happens.',
                  '3. Publish approved pieces manually or through a connected account.',
                  '4. After a week, import actual performance and run the weekly editorial workflow.',
                  '5. Return stronger angles to the idea bank when the evidence supports a winner.', '',
                  'This plan has not scheduled or published anything. Performance learning starts from real observations.', '']
        atomic_text(self.store.data / 'creator/LAUNCH_PLAN.md', '\n'.join(lines))
