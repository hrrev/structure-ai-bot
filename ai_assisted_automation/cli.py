import argparse
import json
import sys

from ai_assisted_automation.models.workflow import Workflow
from ai_assisted_automation.storage.json_store import JsonStore


def cmd_serve(args):
    import os

    import uvicorn
    from ai_assisted_automation.api.app import create_app

    tool_configs = {
        "youtube_search": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "youtube_video_stats": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "newsapi_search": {"auth_token": os.environ.get("NEWSAPI_KEY", "")},
        "api_ninjas_sentiment": {"auth_token": os.environ.get("API_NINJAS_KEY", "")},
        "api_ninjas_celebrity": {"auth_token": os.environ.get("API_NINJAS_KEY", "")},
        "github_graphql_repo": {"auth_token": os.environ.get("GITHUB_PAT", "")},
        "github_graphql_create_issue": {"auth_token": os.environ.get("GITHUB_PAT", "")},
        "github_graphql_add_comment": {"auth_token": os.environ.get("GITHUB_PAT", "")},
        "github_create_anime_report": {"auth_token": os.environ.get("GITHUB_PAT", "")},
        "github_add_anime_comment": {"auth_token": os.environ.get("GITHUB_PAT", "")},
    }

    app = create_app(data_dir=args.data_dir, tools_dir=args.tools_dir, tool_configs=tool_configs)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def cmd_plan(args):
    import asyncio

    from ai_assisted_automation.planner import InsufficientTools, plan
    from ai_assisted_automation.registry.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.load_directory(args.tools_dir)

    result = asyncio.run(plan(args.goal, registry, max_retries=args.max_retries))

    if isinstance(result, InsufficientTools):
        print(f"Cannot plan workflow: {result.reason}")
        print(f"Missing capabilities: {', '.join(result.missing_capabilities)}")
        sys.exit(1)

    # Save to store and print
    store = JsonStore(args.data_dir)
    store.save_workflow(result)
    print(f"Workflow generated and saved: {result.id} ({result.name})")
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


def cmd_register(args):
    store = JsonStore(args.data_dir)
    data = json.loads(open(args.file).read())
    wf = Workflow.model_validate(data)
    store.save_workflow(wf)
    print(f"Registered workflow: {wf.id} ({wf.name})")


def main():
    parser = argparse.ArgumentParser(prog="aaa", description="Workflow Automation Engine")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start the web server")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--data-dir", default="data")
    serve_p.add_argument("--tools-dir", default="tools")

    plan_p = sub.add_parser("plan", help="Generate a workflow from natural language")
    plan_p.add_argument("goal", help="What the workflow should accomplish")
    plan_p.add_argument("--tools-dir", default="tools")
    plan_p.add_argument("--data-dir", default="data")
    plan_p.add_argument("--max-retries", type=int, default=3)

    reg_p = sub.add_parser("register", help="Register a workflow from JSON")
    reg_p.add_argument("file", help="Path to workflow JSON file")
    reg_p.add_argument("--data-dir", default="data")

    args = parser.parse_args()
    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "register":
        cmd_register(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
