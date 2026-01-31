"""
Workflow: GitHub Repo Intelligence Report

Graph:
                $input.owner + $input.repo
                          │
                       step_1 (repo info)
                 ╱    ╱        ╲       ╲
           step_2  step_3   step_4   step_5
           contribs releases issues  commit_activity
                 ╲    ╲        ╱       ╱
                       step_6 (POST summary to httpbin)

6 steps, fan-out from step_1, fan-in at step_6.
Every step_6 input maps a field from a predecessor.

Requires: GITHUB_TOKEN env var (free personal access token).
Without it, GitHub allows 60 req/hr (enough for one run).
"""

import json
import os

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.workflow import Edge, Step, Workflow
from ai_assisted_automation.registry.tool_registry import ToolRegistry


def build_workflow() -> Workflow:
    return Workflow(
        id="github_intel",
        name="GitHub Repo Intelligence Report",
        steps=[
            Step(
                id="step_1",
                tool_id="github_repo",
                input_mapping={
                    "owner": "$input.owner",
                    "repo": "$input.repo",
                },
                description="Get repo metadata",
            ),
            Step(
                id="step_2",
                tool_id="github_contributors",
                input_mapping={
                    "owner": "$input.owner",
                    "repo": "$input.repo",
                    "per_page": "5",
                },
                description="Get top 5 contributors",
            ),
            Step(
                id="step_3",
                tool_id="github_releases",
                input_mapping={
                    "owner": "$input.owner",
                    "repo": "$input.repo",
                    "per_page": "3",
                },
                description="Get 3 most recent releases",
            ),
            Step(
                id="step_4",
                tool_id="github_issues",
                input_mapping={
                    "owner": "$input.owner",
                    "repo": "$input.repo",
                    "state": "open",
                    "per_page": "5",
                },
                description="Get 5 most recent open issues",
            ),
            Step(
                id="step_5",
                tool_id="github_commit_activity",
                input_mapping={
                    "owner": "$input.owner",
                    "repo": "$input.repo",
                },
                description="Get weekly commit activity",
            ),
            Step(
                id="step_6",
                tool_id="httpbin_post",
                input_mapping={
                    "repo_full_name": "step_1.full_name",
                    "stars": "step_1.stargazers_count",
                    "language": "step_1.language",
                    "open_issues_count": "step_1.open_issues_count",
                    "top_contributor": "step_2.items.0.login",
                    "top_contributor_commits": "step_2.items.0.contributions",
                    "latest_release_tag": "step_3.items.0.tag_name",
                    "latest_release_name": "step_3.items.0.name",
                    "newest_issue_title": "step_4.items.0.title",
                    "newest_issue_url": "step_4.items.0.html_url",
                },
                description="POST intelligence summary to webhook",
            ),
        ],
        edges=[
            Edge(from_step_id="step_1", to_step_id="step_2"),
            Edge(from_step_id="step_1", to_step_id="step_3"),
            Edge(from_step_id="step_1", to_step_id="step_4"),
            Edge(from_step_id="step_1", to_step_id="step_5"),
            Edge(from_step_id="step_2", to_step_id="step_6"),
            Edge(from_step_id="step_3", to_step_id="step_6"),
            Edge(from_step_id="step_4", to_step_id="step_6"),
            Edge(from_step_id="step_5", to_step_id="step_6"),
        ],
    )


def main():
    registry = ToolRegistry()
    registry.load_directory("tools")

    gh_token = os.environ.get("GITHUB_TOKEN", "")
    github_auth = {"auth_token": gh_token}
    tool_configs = {
        "github_repo": github_auth,
        "github_contributors": github_auth,
        "github_releases": github_auth,
        "github_issues": github_auth,
        "github_commit_activity": github_auth,
    }

    workflow = build_workflow()
    owner = input("GitHub owner (e.g. 'fastapi'): ").strip() or "fastapi"
    repo = input("GitHub repo  (e.g. 'fastapi'): ").strip() or "fastapi"

    print(f"\n=== Running: {workflow.name} for {owner}/{repo} ===\n")

    run = execute(
        workflow,
        {"owner": owner, "repo": repo},
        registry.get_tool_map(),
        tool_configs,
    )

    print(f"=== Run result: {run.status.value} ===")
    for r in run.step_results:
        print(f"\n--- {r.step_id} [{r.status.value}] ---")
        if r.error:
            print(f"  ERROR: {r.error}")
        else:
            print(json.dumps(r.output_data, indent=2, default=str)[:600])


if __name__ == "__main__":
    main()
