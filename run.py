"""Entry point. Starts the web server by default; --cli runs in the terminal."""

import argparse
import sys
import threading
import webbrowser

import agents
import config
import prompts
import runstore
from prompts import AGENT_ALIASES


def banner(model: str, mode: str) -> str:
    return (
        f"\n  {config.APP_NAME}  —  {config.TAGLINE}\n"
        f"  {'-' * 44}\n"
        f"  model: {model}  ({mode})\n"
    )


def cli_event_printer():
    """Terminal progress reporter with the same event contract as the WebSocket."""

    def printer(event: dict) -> None:
        kind = event.get("type")
        if kind == "agent_start":
            meta = prompts.AGENT_META[event["agent"]]
            print(
                f"\n{meta['emoji']}  Agent {event['step']}/{event['total']}: "
                f"{meta['name']} — {meta['activity']}..."
            )
        elif kind == "agent_thinking":
            # Reasoning phase: a distinct pulse, so a long think is not mistaken
            # for a hang.
            print("·", end="", flush=True)
        elif kind == "agent_token":
            # A visible pulse without flooding the terminal with the full text.
            print(".", end="", flush=True)
        elif kind == "agent_complete":
            meta = prompts.AGENT_META[event["agent"]]
            print(f"\n   done: {meta['name']} ({len(event['output'].split())} words)")
        elif kind == "pipeline_complete":
            print(f"\n✅  Saved to {event['folder']}")
            for filename in event["files"]:
                print(f"    - {filename}")
            if event["missing_sections"]:
                print(
                    "\n⚠️   The writer's output could not be split into: "
                    f"{', '.join(event['missing_sections'])}."
                    "\n    The full response is in 04-writer-combined.md."
                )
            print(
                "\nNext steps:"
                "\n  1. Read the research brief, then start Phase 1 of the learning path."
                "\n  2. Check the 'Verify before publishing' block in each file before posting."
            )
        elif kind == "cancelled":
            print("\n⛔  Cancelled. Nothing was written.")
        elif kind == "error":
            print(f"\n❌  {event['message']}")
            if event.get("hint"):
                print(f"    → {event['hint']}")

    return printer


def run_cli(topic: str | None, agent: str | None) -> int:
    try:
        model, mode = agents.resolve_model()
    except agents.OllamaError as exc:
        print(f"\n❌  {exc}\n    → {exc.hint}")
        return 1

    print(banner(model, mode))

    while True:
        current = topic or input(f"{config.APP_SHORT_NAME} › What do you want to learn about? ")
        current = current.strip()
        if not current:
            print("A topic is required.")
            if topic:
                return 1
            continue

        printer = cli_event_printer()
        run_id = runstore.mint_run_id(current)
        try:
            if agent:
                key = AGENT_ALIASES[agent]
                printer({"type": "agent_start", "agent": key, "step": 1, "total": 1})
                text = agents.run_agent(
                    key, current, {}, model=model, temperature=config.TEMPERATURE
                )
                printer({"type": "agent_complete", "agent": key, "step": 1, "output": text})
                print("\n" + text)
            else:
                agents.run_pipeline(current, on_event=printer, run_id=run_id)
        except agents.RunCancelled:
            return 130
        except agents.OllamaError as exc:
            # run_pipeline already emitted the error event; single-agent mode did not.
            if agent:
                print(f"\n❌  {exc}\n    → {exc.hint}")
            return 1

        if topic:
            return 0
        if input("\nExplore another topic? [y/N] ").strip().lower() != "y":
            return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="run.py", description=f"{config.APP_NAME} — {config.TAGLINE}"
    )
    parser.add_argument("--cli", action="store_true", help="run in the terminal")
    parser.add_argument("--topic", help="topic to explore (CLI mode)")
    parser.add_argument(
        "--agent", choices=sorted(AGENT_ALIASES), help="run a single agent (CLI mode)"
    )
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.cli:
        return run_cli(args.topic, args.agent)

    import uvicorn

    from server import app

    # Port 8000 is often already taken; pick the next free one rather than
    # failing with a bind traceback.
    port = config.find_free_port(args.port)
    url = f"http://{config.HOST}:{port}"
    if port != args.port:
        print(f"  port {args.port} is in use — using {port} instead")

    status = agents.preflight()
    print(banner(status.get("model", config.MODEL_NAME), status.get("mode", "unknown")))
    if not status["ollama"]:
        print(f"  ⚠️  {status['error']}\n      → {status.get('hint', '')}")
    print(f"  {config.APP_SHORT_NAME} is running at {url}\n")

    if not args.no_browser:
        # Open only once the server is actually accepting connections.
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host=config.HOST, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
