"""Single entry point for the exam-bank skill.

Usage: python .claude/skills/exam-bank/scripts/eb.py <command> <exam> [args...]
"""

import argparse
import pathlib
import sys

# Run config and environment checks first, even on an older interpreter.
if sys.version_info < (3, 11):
    if len(sys.argv) >= 3 and sys.argv[1] == 'setup':
        import setup
        import store
        try:
            setup.check_config(pathlib.Path.cwd(), sys.argv[2])
        except store.Stop as error:
            print(error, file=sys.stderr)
            sys.exit(1)
    print('Python 3.11 or newer is required. Install it and rerun setup.', file=sys.stderr)
    sys.exit(1)

import augment
import batches
import export
import fetch
import intake
import merge
import scrape
import setup
import state
import store

COMMANDS = (
    "state",
    "setup",
    "scrape",
    "fetch",
    "intake",
    "merge",
    "batches",
    "apply",
    "augment-plan",
    "export",
    "study-guide-plan",
    "study-guide-check",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eb.py", description="exam-bank entry point")
    parser.add_argument("command", choices=COMMANDS, metavar="command",
                        help="one of: " + ", ".join(COMMANDS))
    parser.add_argument("exam", help="exam slug, for example pmle")
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="command-specific arguments")
    return parser


# Each built step takes (root, exam, now) and returns the text to print.
STEPS = {"setup": setup.run, "intake": intake.run, "scrape": scrape.run, "fetch": fetch.run,
         "merge": merge.run, "export": export.run}


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if ns.command in ('batches', 'apply'):
        if len(ns.args) != 1:
            print(f'{ns.command} requires one dispatch step', file=sys.stderr)
            return 1
        try:
            command = batches.run if ns.command == 'batches' else batches.apply
            print(command(pathlib.Path.cwd(), ns.exam, store.now_utc(), ns.args[0]))
        except (store.Stop, OSError) as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    if ns.command in ('study-guide-plan', 'study-guide-check'):
        args = ns.args
        if ns.command == 'study-guide-check' and len(args) != 1:
            print('study-guide-check requires one Subdomain', file=sys.stderr)
            return 1
        if ns.command == 'study-guide-plan' and (len(args) > 2 or
                (len(args) == 2 and (args[0] == 'redo' or args[1] != 'redo'))):
            print('study-guide-plan accepts [<subdomain>] [redo]', file=sys.stderr)
            return 1
        try:
            import study_guide
            if ns.command == 'study-guide-check':
                out = study_guide.check(pathlib.Path.cwd(), ns.exam, store.now_utc(), args[0])
            else:
                subdomain = args[0] if args and args[0] != 'redo' else None
                out = study_guide.plan(pathlib.Path.cwd(), ns.exam, store.now_utc(),
                                       subdomain, bool(args and args[-1] == 'redo'))
            print(out)
        except ImportError as error:
            print(f'Missing dependency: {error}. Run pip install -r requirements.txt.', file=sys.stderr)
            return 1
        except (store.Stop, OSError) as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    if ns.command == 'augment-plan':
        if len(ns.args) > 1:
            print('augment-plan accepts at most one answer, yes or no', file=sys.stderr)
            return 1
        try:
            print(augment.plan(pathlib.Path.cwd(), ns.exam, store.now_utc(), ns.args[0] if ns.args else None))
        except (store.Stop, OSError) as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    if ns.command == 'state':
        if len(ns.args) > 1:
            print('state accepts at most one step', file=sys.stderr)
            return 1
        try:
            print(state.run(pathlib.Path.cwd(), ns.exam, store.now_utc(), ns.args[0] if ns.args else None))
        except (store.Stop, OSError) as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    step = STEPS.get(ns.command)
    if step is None:
        print(f"not implemented yet: {ns.command} {ns.exam}", file=sys.stderr)
        return 1
    if ns.args:
        print(f"not implemented yet: {ns.command} arguments {' '.join(ns.args)}",
              file=sys.stderr)
        return 1
    try:
        # The data folder sits under the directory the command runs from, the repo root.
        print(step(pathlib.Path.cwd(), ns.exam, store.now_utc()))
    except store.Stop as stop:
        print(stop, file=sys.stderr)
        return 1
    except OSError as error:
        # For example the CSV is open in a spreadsheet program on Windows.
        print(f"{ns.command} stopped, a file could not be written: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
