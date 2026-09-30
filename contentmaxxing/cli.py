"""Thin, testable CLI over shared engine operations. JSON output is scriptable."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import ValidationError

from .analytics import inspect_measurement, winners
from .connectors.typefully import TypefullyConnector
from .engine import Engine
from .feedback import CATEGORIES, SCOPES, Feedback
from .retrieval import SourceLibrary
from .mining import MiningIncomplete, source_progress
from .revisions import Revisions
from .kickoff import Kickoff
from .installation import HOSTS, doctor, install, menu, uninstall
from .overview import overview
from .planning import Planning
from .welcome import BANNER, welcome
from .export import export_workspace
from .providers import PendingTask
from .publishing import Publishing
from .scheduler import Scheduler
from .store import Store, atomic_json


def parser():
    p = argparse.ArgumentParser(prog='contentmaxxing', description='Capture → Create → Compound. Portable creator intelligence.')
    p.add_argument('--workspace', help='Creator folder (default: current directory; start uses my-creator inside this repository)')
    p.add_argument('--provider', dest='execution_provider', choices=['external', 'extractive', 'openai-compatible'], help='Override execution for this command')
    p.add_argument('--json', dest='json_output', action='store_true', help='Keep welcome/install output machine-readable')
    commands = p.add_subparsers(dest='command', required=True)
    evals = commands.add_parser('evals', help='Portable editorial evaluations; no model or publishing calls').add_subparsers(dest='action', required=True)
    prep = evals.add_parser('prepare')
    prep.add_argument('--output', required=True)
    prep.add_argument('--label', required=True)
    prep.add_argument('--suite', help='Custom suite JSON; defaults to six fictional editorial cases')
    prep.add_argument('--intelligence', help='Intelligence root containing skills/, prompts/ and templates/')
    prep.add_argument('--max-attempts', type=int, default=1)
    submit = evals.add_parser('submit')
    submit.add_argument('--run', required=True); submit.add_argument('--case', required=True); submit.add_argument('--file', required=True)
    grade = evals.add_parser('grade')
    grade.add_argument('--run', required=True); grade.add_argument('--case', required=True)
    grade.add_argument('--verdict', choices=['pass', 'fail'], required=True)
    grade.add_argument('--reviewer', required=True); grade.add_argument('--note', required=True)
    ev_report = evals.add_parser('report'); ev_report.add_argument('--run', required=True)
    comparison = evals.add_parser('compare')
    comparison.add_argument('--baseline', required=True); comparison.add_argument('--candidate', required=True)
    for operation in ('install', 'uninstall', 'doctor'):
        setup = commands.add_parser(operation, help=operation.title() + ' native AI skills and commands')
        setup.add_argument('--agent', choices=HOSTS, required=True)
        setup.add_argument('--scope', choices=['project', 'user'], default='project')
        setup.add_argument('--path', help='Project to install into (default: current folder); user scope uses your home')
        if operation != 'doctor':
            setup.add_argument('--dry-run', action='store_true')
    command_menu = commands.add_parser('commands', help='Show the creator-facing AI command menu')
    command_menu.add_argument('--agent', choices=HOSTS, default='generic')
    upgrade = commands.add_parser('upgrade', help='Update workspace intelligence while preserving customizations and creator data')
    upgrade.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    upgrade.add_argument('--adopt-matching', action='store_true', help='Track existing files only when they exactly match this bundle')
    upgrade.add_argument('--accept', action='append', default=[], metavar='FILE=TOKEN', help='Replace a reviewed file using the token from --review')
    maintenance = upgrade.add_mutually_exclusive_group()
    maintenance.add_argument('--review', metavar='FILE', help='Read-only diff and acceptance token for a bundled relative path')
    maintenance.add_argument('--recover', metavar='UPGRADE_ID', help='Roll back an interrupted upgrade without replacing later edits')
    commands.add_parser('overview', help='Read-only setup and content progress')
    for name in ('home', 'progress', 'next', 'resume'):
        commands.add_parser(name, help='Read saved progress and return the next agent action (read-only)')
    commands.add_parser('welcome', help='Show the CONTENTMAXXING home screen and onboarding choices')
    start = commands.add_parser('start', help='Start or resume an agent-led creator kickoff')
    start.add_argument('--answers', help='Agent-prepared partial creator profile JSON')
    start.add_argument('--mode', choices=['interview', 'files'], help='Choose guided interview or bulk source intake')
    start.add_argument('--source', action='append', help='Source file or directory; repeat for multiple drops')
    start.add_argument('--profile-proposal', help='Agent-prepared profile proposal with exact file/line evidence')
    start.add_argument('--confirm-profile', action='store_true', help='Record creator confirmation of a file-derived profile')
    start.add_argument('--batch-size', type=int, help='First batch target (default: 3; source quality can reduce it)')
    start.add_argument('--platform', help='First platform to focus on')
    start.add_argument('--idea', action='append', help='Editorial selection; repeat for each chosen idea')
    start.add_argument('--timezone', default='UTC', help='Timezone when creating a workspace')
    init = commands.add_parser('init')
    init.add_argument('--provider', default='external', choices=['external', 'extractive', 'openai-compatible'])
    init.add_argument('--timezone', default='UTC')
    onboard = commands.add_parser('onboard')
    choice = onboard.add_mutually_exclusive_group()
    choice.add_argument('--profile', help='Creator profile JSON')
    choice.add_argument('--template', help='Write a complete blank questionnaire JSON file')
    voice = commands.add_parser('voice', help='Learn from creator samples; review and apply portable voice observations').add_subparsers(dest='action', required=True)
    learn = voice.add_parser('learn')
    learn.add_argument('--samples', help='JSON array of explicitly attributed captured excerpts; profile writing is also included')
    learn.add_argument('--new', action='store_true', help='Create a new analysis from current evidence')
    voice.add_parser('list')
    for name in ('show', 'apply', 'dismiss'):
        entry = voice.add_parser(name)
        entry.add_argument('proposal_id')
        if name == 'dismiss':
            entry.add_argument('--reason', required=True)
    capture = commands.add_parser('capture')
    capture.add_argument('file')
    capture.add_argument('--kind', default='transcript')
    capture.add_argument('--consent', default='unspecified')
    capture.add_argument('--notes', default='')
    sources = commands.add_parser('sources', help='Search captured evidence with original citations').add_subparsers(dest='action', required=True)
    sources.add_parser('list')
    search = sources.add_parser('search')
    search.add_argument('query'); search.add_argument('--source', action='append')
    search.add_argument('--kind'); search.add_argument('--limit', type=int, default=8)
    search.add_argument('--max-chars', type=int, default=12000)
    source_read = sources.add_parser('read')
    source_read.add_argument('source_id'); source_read.add_argument('--start-line', type=int, required=True)
    source_read.add_argument('--end-line', type=int, required=True)
    source_read.add_argument('--max-chars', type=int, default=12000)
    mine = commands.add_parser('mine')
    mine.add_argument('source', help='Captured source ID or text file path')
    mine.add_argument('--restart', action='store_true', help='Start a new pass after completing the saved long-source pass')
    mine.add_argument('--retry', action='store_true', help='Retry a saved pending chunk using its configured provider')
    mining = commands.add_parser('mining', help='Read saved source mining progress')
    mining.add_argument('source_id', nargs='?')
    ideas = commands.add_parser('ideas').add_subparsers(dest='action', required=True)
    listing = ideas.add_parser('list')
    listing.add_argument('--status')
    listing.add_argument('--query', default='')
    listing.add_argument('--platform')
    listing.add_argument('--job')
    select = ideas.add_parser('select')
    select.add_argument('idea_id')
    select.add_argument('--platform', default='x')
    select.add_argument('--format')
    select.add_argument('--job')
    cite = ideas.add_parser('cite', help='Attach additional exact evidence before drafting')
    cite.add_argument('idea_id'); cite.add_argument('--source', required=True)
    cite.add_argument('--start-line', type=int, required=True); cite.add_argument('--end-line', type=int, required=True)
    cite.add_argument('--quote', required=True)
    resolve = ideas.add_parser('resolve', help='Resolve follow-up evidence gaps with cited captured material')
    resolve.add_argument('idea_id'); resolve.add_argument('--file', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('period', choices=['week'])
    plan.add_argument('--new', action='store_true', help='Request a new editorial proposal instead of resuming the saved one')
    create = commands.add_parser('create', help='Execute or resume a saved editorial plan')
    create.add_argument('--plan', help='Saved plan ID; inferred only when exactly one is unfinished')
    draft = commands.add_parser('draft')
    draft.add_argument('platform', choices=['x', 'linkedin', 'tiktok', 'substack', 'substack_note'])
    draft.add_argument('--idea', required=True)
    draft.add_argument('--format')
    draft.add_argument('--job')
    article = commands.add_parser('article')
    article.add_argument('--idea', required=True)
    article.add_argument('--platform', choices=['x_article', 'substack'], default='x_article')
    article.add_argument('--job', default='Authority')
    tasks = commands.add_parser('tasks').add_subparsers(dest='action', required=True)
    tasks.add_parser('list')
    show = tasks.add_parser('show'); show.add_argument('task_id')
    complete = tasks.add_parser('complete'); complete.add_argument('task_id'); complete.add_argument('result_file')
    refresh = tasks.add_parser('refresh-feedback'); refresh.add_argument('task_id')
    cancel = tasks.add_parser('cancel', help='Abandon a pending local revision or compound task')
    cancel.add_argument('task_id'); cancel.add_argument('--reason', required=True)
    task_cite = tasks.add_parser('cite', help='Add exact evidence to an uncommitted pending draft or compound task')
    task_cite.add_argument('task_id'); task_cite.add_argument('--source', required=True)
    task_cite.add_argument('--start-line', type=int, required=True); task_cite.add_argument('--end-line', type=int, required=True)
    task_cite.add_argument('--quote', required=True)
    review = commands.add_parser('review')
    review.add_argument('content_id', nargs='?')
    review.add_argument('--approve', action='store_true')
    edit = commands.add_parser('edit'); edit.add_argument('content_id'); edit.add_argument('--file', required=True)
    revise = commands.add_parser('revise', help='Revise an existing local draft from creator direction/feedback')
    revise.add_argument('content_id'); revise.add_argument('--direction', default='')
    revisions = commands.add_parser('revisions', help='Read before/after revision history')
    revisions.add_argument('content_id')
    feedback = commands.add_parser('feedback', help='Persist explicit creator corrections and preferences').add_subparsers(dest='action', required=True)
    feedback_list = feedback.add_parser('list')
    feedback_list.add_argument('--content'); feedback_list.add_argument('--scope', choices=SCOPES)
    feedback_list.add_argument('--status', choices=['ACTIVE', 'RETIRED'])
    feedback_add = feedback.add_parser('add')
    feedback_add.add_argument('content_id'); feedback_add.add_argument('--note', required=True)
    feedback_add.add_argument('--by', required=True, help='Declared creator/reviewer; not identity verification')
    feedback_add.add_argument('--scope', choices=SCOPES, default='content')
    feedback_add.add_argument('--category', choices=CATEGORIES, default='other')
    feedback_add.add_argument('--excerpt'); feedback_add.add_argument('--replacement')
    retire = feedback.add_parser('retire')
    retire.add_argument('feedback_id'); retire.add_argument('--reason', required=True)
    status = commands.add_parser('status')
    status.add_argument('content_id'); status.add_argument('status', choices=['NEEDS_REVIEW', 'APPROVED', 'SCHEDULED', 'PUBLISHED', 'COMPOUND', 'ARCHIVED'])
    status.add_argument('--url'); status.add_argument('--published-at'); status.add_argument('--at')
    analytics = commands.add_parser('analytics').add_subparsers(dest='action', required=True)
    imp = analytics.add_parser('import'); imp.add_argument('file')
    manual = analytics.add_parser('manual'); manual.add_argument('content_id'); manual.add_argument('--file', required=True); manual.add_argument('--observed-at')
    sync = analytics.add_parser('sync'); sync.add_argument('connector', choices=['typefully']); sync.add_argument('--start'); sync.add_argument('--end')
    winner_list = analytics.add_parser('winners'); winner_list.add_argument('--as-of')
    observation = analytics.add_parser('show', help='Inspect latest values, conflicts and original measurements')
    observation.add_argument('content_id'); observation.add_argument('--as-of')
    report = commands.add_parser('report'); report.add_argument('period', choices=['weekly']); report.add_argument('--as-of')
    compound = commands.add_parser('compound'); compound.add_argument('content_id')
    compound.add_argument('--new', action='store_true', help='Develop another set of angles using current evidence')
    compound.add_argument('--query', default='', help='Terms for retrieving relevant additional source evidence')
    compound.add_argument('--as-of', help='Bound the observation cutoff for a new analysis; existing tasks stay frozen')
    run = commands.add_parser('run'); run.add_argument('workflow', nargs='?', default='weekly-editorial'); run.add_argument('--run-id')
    workflows = commands.add_parser('workflows'); workflows.add_argument('action', choices=['list'], default='list', nargs='?')
    experiments = commands.add_parser('experiments').add_subparsers(dest='action', required=True)
    experiments.add_parser('list')
    exp = experiments.add_parser('save'); exp.add_argument('file', help='Experiment JSON; include id to update existing experiment')
    measure = experiments.add_parser('measure', help='Read-only descriptive measurements, without causal claims')
    measure.add_argument('experiment_id'); measure.add_argument('--as-of')
    export = commands.add_parser('export'); export.add_argument('--output', required=True)
    connect = commands.add_parser('connect').add_subparsers(dest='action', required=True)
    connect.add_parser('accounts'); connect.add_parser('drafts')
    queue = connect.add_parser('queue'); queue.add_argument('--start'); queue.add_argument('--end')
    deliver = connect.add_parser('deliver'); deliver.add_argument('content_id'); deliver.add_argument('--action', choices=['draft', 'schedule', 'publish'], default='draft'); deliver.add_argument('--at')
    reconcile = connect.add_parser('reconcile'); reconcile.add_argument('content_id'); reconcile.add_argument('--remote-id')
    return p


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dates(args):
    end = args.end or datetime.now(timezone.utc).date().isoformat()
    start = args.start or (datetime.fromisoformat(end) - timedelta(days=7)).date().isoformat()
    return start, end


def dispatch(args):
    if args.command == 'evals':
        from .evaluation import Evaluation, compare, prepare
        if args.workspace is not None or args.execution_provider is not None:
            raise ValueError('Evaluations use isolated --run/--output folders and external host execution; omit --workspace/--provider.')
        if args.action == 'prepare':
            return prepare(args.output, args.label, args.suite, args.intelligence, args.max_attempts)
        if args.action == 'compare':
            return compare(args.baseline, args.candidate)
        run = Evaluation(args.run)
        if args.action == 'submit':
            return run.submit_file(args.case, args.file)
        if args.action == 'grade':
            return run.grade(args.case, args.verdict, args.reviewer, args.note)
        return run.report()
    if args.command == 'welcome':
        return welcome()
    if args.command in ('install', 'uninstall', 'doctor'):
        if args.workspace is not None:
            raise ValueError('Use --path for host installation commands, not --workspace.')
        operation = {'install': install, 'uninstall': uninstall, 'doctor': doctor}[args.command]
        options = {'path': args.path, 'scope': args.scope}
        if args.command != 'doctor':
            options['dry_run'] = args.dry_run
        return operation(args.agent, **options)
    if args.command == 'commands':
        return menu(args.agent)
    if args.workspace is None:
        in_repository = (Path.cwd() / 'contentmaxxing/orchestrator.md').is_file()
        args.workspace = str(Path.cwd() / 'my-creator') if args.command in ('start', 'home', 'progress', 'next', 'resume', 'overview') and in_repository else '.'
    engine = Engine(args.workspace, provider_name=args.execution_provider)
    store = engine.store
    command = args.command
    if command in ('overview', 'home', 'progress', 'next', 'resume'):
        return overview(args.workspace)
    if command == 'start':
        return Kickoff(engine).run(answers=read_json(args.answers) if args.answers else None,
            sources=args.source, batch_size=args.batch_size, platform=args.platform,
            idea_ids=args.idea, timezone_name=args.timezone, mode=args.mode,
            profile_proposal=read_json(args.profile_proposal) if args.profile_proposal else None,
            confirm_profile=args.confirm_profile)
    if command == 'init':
        return {'workspace': str(store.root), 'config': store.init(args.provider, args.timezone)}
    store.config
    if command == 'upgrade':
        from .workspace_assets import WorkspaceUpgrade
        operation = WorkspaceUpgrade(store)
        if args.review or args.recover:
            if args.dry_run or args.adopt_matching or args.accept:
                raise ValueError('--review/--recover cannot be combined with upgrade options.')
            return operation.review(args.review) if args.review else operation.recover(args.recover)
        return operation.run(args.dry_run, args.accept, args.adopt_matching)
    if command == 'onboard':
        if args.template:
            path = Path(args.template)
            if path.exists():
                raise ValueError('Template destination exists; refusing to overwrite.')
            atomic_json(path, engine.profile_template())
            return {'questionnaire': str(path.resolve()), 'next': 'Fill it in, then onboard --profile <file>'}
        if args.profile:
            return engine.onboard(read_json(args.profile))
        profile = engine.profile_template()
        for key, default in profile.items():
            raw = input(key.replace('_', ' ') + (' (JSON)' if isinstance(default, (dict, list)) else '') + ': ').strip()
            profile[key] = json.loads(raw) if raw and isinstance(default, (dict, list)) else (raw if isinstance(default, str) else default)
        return engine.onboard(profile)
    if command == 'capture':
        return engine.capture(args.file, args.kind, args.consent, args.notes)
    if command == 'sources':
        library = SourceLibrary(store)
        if args.action == 'list':
            return store.list('sources')
        if args.action == 'search':
            return library.search(args.query, args.source, args.kind, args.limit, args.max_chars)
        return library.read(args.source_id, args.start_line, args.end_line, args.max_chars)
    if command == 'mine':
        source_id = engine.capture(args.source)['id'] if Path(args.source).is_file() else args.source
        return engine.mine(source_id, restart=args.restart, retry=args.retry)
    if command == 'mining':
        return source_progress(store, args.source_id)
    if command == 'ideas':
        if args.action == 'resolve':
            return engine.resolve_idea(args.idea_id, read_json(args.file))
        if args.action == 'select':
            return engine.select(args.idea_id, args.platform, args.format, args.job)
        if args.action == 'cite':
            return engine.cite_idea(args.idea_id, args.source, args.start_line, args.end_line, args.quote)
        return [i for i in store.list('ideas') if (not args.status or i['status'] == args.status) and
                args.query.casefold() in (i['topic'] + ' ' + i['notes']).casefold() and
                (not args.platform or i['best_platform'] == args.platform) and (not args.job or i['primary_job'] == args.job)]
    if command in ('draft', 'article'):
        idea = store.get('ideas', args.idea)
        chosen_format = args.format if command == 'draft' else None
        if idea['status'] == 'BACKLOG' or idea['best_platform'] != args.platform or chosen_format or args.job:
            engine.select(args.idea, args.platform, chosen_format, args.job)
        return engine.draft(args.idea, args.platform)
    if command == 'plan':
        return Planning(engine).plan(fresh=args.new)
    if command == 'create':
        return Planning(engine).create(args.plan)
    if command == 'voice':
        from .voice import Voice
        voice = Voice(engine)
        if args.action == 'learn':
            return voice.request(read_json(args.samples) if args.samples else None, args.new)
        if args.action == 'list':
            return [{k: p[k] for k in ('id', 'task_id', 'status', 'created_at', 'applied_at')} for p in voice.list()]
        if args.action == 'show':
            return voice.get(args.proposal_id)
        if args.action == 'dismiss':
            return voice.dismiss(args.proposal_id, args.reason)
        return voice.apply(args.proposal_id)
    if command == 'tasks':
        if args.action == 'list':
            return [{k: t[k] for k in ['id', 'operation', 'skill', 'status', 'result_ids', 'error']} for t in store.list('tasks')]
        if args.action == 'show':
            return store.get('tasks', args.task_id)
        if args.action == 'refresh-feedback':
            return engine.refresh_feedback(args.task_id)
        if args.action == 'cancel':
            return engine.cancel_task(args.task_id, args.reason)
        if args.action == 'cite':
            return engine.cite_task(args.task_id, args.source, args.start_line, args.end_line, args.quote)
        return engine.complete_task(args.task_id, read_json(args.result_file))
    if command == 'feedback':
        feedback = Feedback(store)
        if args.action == 'list':
            return feedback.list(args.content, args.scope, args.status)
        if args.action == 'retire':
            return feedback.retire(args.feedback_id, args.reason)
        return feedback.add(args.content_id, args.note, args.by, args.scope, args.category,
                            args.excerpt, args.replacement)
    if command == 'review':
        if args.approve:
            if not args.content_id:
                raise ValueError('Approval requires a specific content ID.')
            return engine.transition(args.content_id, 'APPROVED')
        return store.get('content', args.content_id) if args.content_id else [c for c in store.list('content') if c['status'] == 'NEEDS_REVIEW']
    if command == 'edit':
        return engine.edit(args.content_id, Path(args.file).read_text(encoding='utf-8'))
    if command == 'revise':
        return engine.revise(args.content_id, args.direction)
    if command == 'revisions':
        return Revisions(store).history(args.content_id)
    if command == 'status':
        return engine.transition(args.content_id, args.status, args.url, args.published_at, args.at)
    if command == 'analytics':
        if args.action == 'import':
            return engine.import_csv(args.file)
        if args.action == 'manual':
            return engine.manual_metrics(args.content_id, read_json(args.file), args.observed_at)
        if args.action == 'winners':
            return winners(store, args.as_of)
        if args.action == 'show':
            return inspect_measurement(store, args.content_id, args.as_of)
        connector = TypefullyConnector(store.config.get('typefully_social_set_id'))
        return Publishing(engine, connector).sync_analytics(*dates(args))
    if command == 'report':
        return engine.report(args.as_of)
    if command == 'compound':
        return engine.compound(args.content_id, fresh=args.new, query=args.query, as_of=args.as_of)
    if command == 'run':
        return Scheduler(engine).run(args.workflow, args.run_id)
    if command == 'workflows':
        return Scheduler(engine).config()
    if command == 'experiments':
        if args.action == 'list':
            return store.list('experiments')
        if args.action == 'measure':
            return engine.measure_experiment(args.experiment_id, args.as_of)
        return engine.experiment(read_json(args.file))
    if command == 'export':
        return export_workspace(store, args.output)
    if command == 'connect':
        connector = TypefullyConnector(store.config.get('typefully_social_set_id'))
        if args.action == 'accounts':
            return connector.list_accounts()
        if args.action == 'drafts':
            return connector.list_drafts()
        if args.action == 'queue':
            return connector.get_queue(*dates(args))
        publishing = Publishing(engine, connector)
        if args.action == 'deliver':
            return publishing.deliver(args.content_id, args.action, args.at)
        return publishing.reconcile(args.content_id, args.remote_id)
    raise ValueError('Unknown command.')


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = dispatch(args)
        if args.command == 'welcome' and not args.json_output:
            print(BANNER + '\n\nChoose a path in your AI chat. Both paths can be combined.\n')
            return 0
        if args.command == 'install' and not args.dry_run and not args.json_output and sys.stdout.isatty():
            print(BANNER + '\n\nInstalled for ' + result['agent'] + '.\n' + result['next'])
            print('\nWelcome screen: ' + result['welcome']['document'])
            return 0
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except MiningIncomplete as exc:
        print(json.dumps({**exc.progress, 'next': 'Resume with mine <source_id>; the saved pass is not complete.'}, indent=2))
        return 0
    except PendingTask as exc:
        print(json.dumps({'status': 'PENDING', 'task_id': exc.task_id,
                          'task_file': str(Store(args.workspace).path('tasks', exc.task_id)),
                          'next': 'Read tasks show <id>; execute the skill in your agent; tasks complete <id> result.json'}, indent=2))
        return 0
    except (ValueError, ValidationError, OSError, KeyError) as exc:
        message = exc.message if isinstance(exc, ValidationError) else str(exc)
        print(json.dumps({'error': message}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
