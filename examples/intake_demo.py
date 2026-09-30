"""Fictional file-dump walkthrough. No live model or publishing API calls."""
import argparse
import json
from pathlib import Path

from contentmaxxing.engine import Engine
from contentmaxxing.installation import install
from contentmaxxing.kickoff import Kickoff
from contentmaxxing.store import atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    args = parser.parse_args()
    root = Path(args.workspace).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError('Use an empty folder for this fictional demonstration.')
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures'
    installation = install('codex', root)
    engine = Engine(root, provider_name='extractive')
    kickoff = Kickoff(engine)
    phases = [kickoff.run()['phase']]
    state = kickoff.run(mode='files', sources=[fixtures / 'intake', fixtures / 'transcript.txt'])
    phases.append(state['phase'])
    document = next(doc for doc in state['intake']['documents'] if doc['name'] == 'about.md')
    lines = (root / document['path']).read_text().splitlines()
    # Authored from the fictional fixture. A real host infers a proposal and asks
    # the creator to confirm; this demo explicitly simulates that confirmation.
    profile = {'name': 'Morgan Demo', 'audience': 'Independent studio operators',
               'content_goals': ['Share usable working notes'], 'platforms': ['x']}
    proposal = {'profile': profile, 'evidence': [
        {'field': field, 'path': document['path'], 'start_line': line, 'end_line': line,
         'quote': lines[line - 1]} for line, field in enumerate(profile, 1)],
        'unknowns': ['Voice is provisional; more writing samples would help.'], 'conflicts': []}
    phases.append(kickoff.run(profile_proposal=proposal)['phase'])
    state = kickoff.run(confirm_profile=True)
    phases.append(state['phase'])
    selected = []
    for needle in ('save the exact question', 'skipped the handoff owner', 'write down every exception'):
        idea = next(idea for idea in state['candidate_ideas'] if needle in idea['topic'])
        engine.select(idea['id'], 'x', 'short post', 'Conversation')
        selected.append(idea['id'])
    state = kickoff.run(idea_ids=selected)
    phases.append(state['phase'])
    result = {'workspace': str(root), 'phases': phases,
              'preserved_sources': len(engine.store.list('sources')),
              'source_excerpt_drafts': len(state['content_ids']),
              'statuses': [engine.store.get('content', identifier)['status'] for identifier in state['content_ids']],
              'welcome': installation['welcome'],
              'notice': 'Fictional profile and simulated confirmation; extractive source excerpts, no live model or publishing calls.'}
    atomic_json(root / 'intake-demo-result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
