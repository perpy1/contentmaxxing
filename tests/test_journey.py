import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from contentmaxxing.engine import Engine
from contentmaxxing.installation import render
from contentmaxxing.overview import overview
from contentmaxxing.planning import Planning
from contentmaxxing.store import atomic_text
from test_vertical import WorkspaceFixture


class JourneyTests(WorkspaceFixture, unittest.TestCase):
    def config(self, count=2):
        path = self.engine.store.root / 'workflows.yaml'
        cfg = yaml.safe_load(path.read_text())
        cfg['counts'] = {'x': count}
        atomic_text(path, yaml.safe_dump(cfg))

    def finish(self, engine):
        for task in engine.store.list('tasks'):
            if task['status'] == 'COMPLETED':
                continue
            ref = task['inputs']['idea']['source_reference'][0]
            engine.complete_task(task['id'], {'body': ref['quote'], 'title': '',
                'claims': [{'claim': ref['quote'], 'source_reference': ref}],
                'quality_notes': ['Fictional fixture, exact source excerpt.'], 'framework': None})

    def test_home_does_not_write_and_tracks_full_loop(self):
        root = self.engine.store.root
        before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(overview(root)['next_action']['command'], 'plan')
        after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        post = self.post()
        self.assertEqual(overview(root)['stage'], 'REVIEW')
        self.engine.transition(post['id'], 'APPROVED')
        nav = overview(root)
        self.assertEqual(nav['stage'], 'PUBLISH')
        self.assertTrue(nav['next_action']['requires_user_input'])
        self.engine.transition(post['id'], 'PUBLISHED', url='https://example.com/fictional-post')
        self.assertEqual(overview(root)['stage'], 'MEASURE')
        self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 10})
        self.assertEqual(overview(root)['stage'], 'PLAN')

    def test_home_new_workspace_does_not_initialize(self):
        root = self.engine.store.root / 'new'
        self.assertEqual(overview(root)['next_action']['command'], 'start')
        self.assertFalse(root.exists())

    def test_future_schedule_does_not_keep_requesting_publication(self):
        post = self.post()
        self.engine.transition(post['id'], 'APPROVED')
        self.engine.transition(post['id'], 'SCHEDULED', scheduled_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
        nav = overview(self.temp.name)
        self.assertEqual(nav['content_statuses']['SCHEDULED'], 1)
        self.assertEqual(nav['stage'], 'PLAN')

    def test_plan_create_preserves_choices_and_resumes_without_duplicates(self):
        self.config()
        selected = self.engine.select(self.ideas[-1]['id'], format_name='contrarian take', job='Conversation')
        engine = Engine(self.temp.name, provider_name='external')
        planning = Planning(engine)
        plan = Planning(self.engine).plan()  # Legacy/offline plans also execute through a host.
        slot = plan['stages'][0]['slots'][0]
        self.assertEqual((slot['idea_id'], slot['format'], slot['job']),
                         (selected['id'], 'contrarian take', 'Conversation'))
        self.assertEqual(overview(self.temp.name)['next_action']['arguments']['plan_id'], plan['id'])
        result = planning.create(plan['id'])
        self.assertEqual(result['run']['status'], 'WAITING')
        self.assertEqual(len(engine.store.list('content')), 0)
        task_count = len(engine.store.list('tasks'))
        planning.create(plan['id'])
        self.assertEqual(len(engine.store.list('tasks')), task_count)
        self.finish(engine)
        result = planning.create(plan['id'])
        self.assertEqual(result['plan']['status'], 'COMPLETED')
        self.assertEqual(len(result['plan']['content_ids']), 2)
        content = engine.store.list('content')
        self.assertTrue(all(c['status'] == 'NEEDS_REVIEW' for c in content))
        chosen = next(c for c in content if c['idea_id'] == selected['id'])
        self.assertEqual((chosen['format'], chosen['primary_job']), ('contrarian take', 'Conversation'))
        planning.create(plan['id'])
        self.assertEqual(len(engine.store.list('content')), 2)
        self.assertEqual(overview(self.temp.name)['next_action']['command'], 'review')

    def test_plan_recovers_run_saved_before_plan_checkpoint_and_can_move(self):
        self.config(1)
        engine = Engine(self.temp.name, provider_name='external')
        planning = Planning(engine)
        plan = Planning(self.engine).plan()
        with patch.object(planning, 'save', side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                planning.create(plan['id'])
        self.assertEqual(len(engine.store.list('runs')), 1)
        with tempfile.TemporaryDirectory() as folder:
            moved = Path(folder) / 'creator'
            shutil.copytree(self.temp.name, moved)
            restored = Engine(moved, provider_name='external')
            result = Planning(restored).create(plan['id'])
            self.assertEqual(result['run']['status'], 'WAITING')
            self.assertEqual(len(restored.store.list('runs')), 1)
            self.finish(restored)
            Planning(restored).create(plan['id'])
            self.assertEqual(len(restored.store.list('content')), 1)

    def test_task_recovery_does_not_use_incompatible_old_completed_draft(self):
        self.config(1)
        planning = Planning(self.engine)
        plan = planning.plan()
        idea_id = plan['stages'][0]['slots'][0]['idea_id']
        self.engine.select(idea_id, format_name='checklist', job='Bookmarks / Saves')
        previous = self.engine.draft(idea_id)[0]
        result = planning.create(plan['id'])
        post = self.engine.store.get('content', result['plan']['content_ids'][0])
        self.assertNotEqual(post['id'], previous['id'])
        self.assertEqual(post['format'], plan['stages'][0]['slots'][0]['format'])

    def test_ambiguous_plans_require_selection_and_invalid_plan_is_preflighted(self):
        self.config(1)
        planning = Planning(self.engine)
        planning.plan()
        plan = planning.plan()
        self.assertEqual(overview(self.temp.name)['next_action']['command'], 'resume')
        self.assertTrue(overview(self.temp.name)['next_action']['requires_user_input'])
        with self.assertRaisesRegex(ValueError, 'Choose a saved plan'):
            planning.create()
        plan['stages'][0]['slots'][0]['job'] = 'made up job'
        planning.save(plan)
        with self.assertRaisesRegex(ValueError, 'invalid format or job'):
            planning.create(plan['id'])
        self.assertEqual(self.engine.store.list('runs'), [])
        self.assertEqual(self.engine.store.list('content'), [])

    def test_cannot_silently_change_plan_during_execution(self):
        self.config(1)
        planning = Planning(Engine(self.temp.name, provider_name='external'))
        plan = Planning(self.engine).plan()
        planning.create(plan['id'])
        plan['stages'][0]['slots'][0]['job'] = 'Trust'
        planning.save(plan)
        with self.assertRaisesRegex(ValueError, 'Plan changed'):
            planning.create(plan['id'])

    def test_empty_plan_reports_no_drafts_and_source_shortfall(self):
        self.config(2)
        for idea in self.engine.store.list('ideas'):
            idea['status'] = 'ARCHIVED'
            self.engine.store.put('ideas', idea)
        planning = Planning(self.engine)
        plan = planning.plan()
        result = planning.create(plan['id'])
        self.assertEqual(result['plan']['content_ids'], [])
        self.assertEqual(result['plan']['stages'][0]['shortfall'], 2)
        self.assertEqual(overview(self.temp.name)['stage'], 'CAPTURE')

    def test_winner_route_returns_to_idea_bank_after_compounding(self):
        ids = []
        for index in range(5):
            post = self.publish(self.post(index))
            ids.append(post['id'])
            self.engine.manual_metrics(post['id'], {'impressions': 1000, 'bookmarks': 40 if index == 0 else 4})
        nav = overview(self.temp.name)
        self.assertEqual(nav['stage'], 'COMPOUND')
        self.assertEqual(nav['next_action']['arguments']['content_ids'], ids[:1])
        self.engine.compound(ids[0])
        self.assertEqual(overview(self.temp.name)['stage'], 'PLAN')

    def test_umbrella_opens_contextual_home_and_keeps_menu_in_help(self):
        files = render('codex')
        umbrella = files['.agents/skills/contentmaxxing/SKILL.md']
        self.assertIn('read-only `home`', umbrella)
        self.assertNotIn('| Command |', umbrella)
        self.assertIn('| Command |', files['.agents/skills/contentmaxxing-help/SKILL.md'])
        self.assertIn('commands/create.md', files['.agents/skills/contentmaxxing-create/SKILL.md'])
