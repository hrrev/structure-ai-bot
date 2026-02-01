"""
Workflow: Anime Intelligence Report (GraphQL + REST)

Graph:
    $input.anime_name
       ┌──────────┬──────────────┬──────────────┐
    step_1       step_2        step_4         step_6
    AniList      Wikipedia     Countries      YouTube
    GraphQL      REST          GraphQL        REST
    (anime       (summary)     (JP info)      (search)
    metadata)       |              |              |
       |         step_3         step_5         step_7
       |         Sentiment      R&M GraphQL    Video Stats
       |         REST           (character     REST
       |         (on summary)   by name)          |
       |            |              |              |
       └────────────┴──────┬───────┴──────────────┘
                           |             step_8
                           |             GitHub GraphQL QUERY
                           |             (get repo node ID)
                           |                  |
                           └──────┬───────────┘
                                  |
                               step_9
                               GitHub GraphQL MUTATION
                               (create issue — fan-in from ALL)
                                  |
                               step_10
                               GitHub GraphQL MUTATION
                               (add comment with enrichment)

10 steps, 3 GraphQL APIs + 4 REST APIs, fan-out/fan-in, chained mutations.

Requires env vars: YOUTUBE_API_KEY, API_NINJAS_KEY, GITHUB_PAT
"""

import json
import os
import sys

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.workflow import Edge, Step, StepSeverity, StepValidation, Workflow
from ai_assisted_automation.registry.tool_registry import ToolRegistry


def build_workflow() -> Workflow:
    return Workflow(
        id="anime_intel_graphql",
        name="Anime Intelligence Report (GraphQL + REST)",
        steps=[
            # step_1: AniList GraphQL — anime metadata
            Step(
                id="step_1",
                tool_id="anilist_anime",
                input_mapping={"search": "$input.anime_name"},
                description="Search AniList for anime metadata via GraphQL",
                name="AniList Lookup",
            ),
            # step_2: Wikipedia REST — anime summary
            Step(
                id="step_2",
                tool_id="wikipedia_summary",
                input_mapping={"title": "$input.anime_name"},
                description="Get Wikipedia summary for the anime",
                name="Wikipedia Summary",
            ),
            # step_3: Sentiment on Wikipedia summary (depends on step_2)
            Step(
                id="step_3",
                tool_id="api_ninjas_sentiment",
                input_mapping={"text": "step_2.summary"},
                description="Analyze sentiment of Wikipedia summary",
                name="Wiki Sentiment",
            ),
            # step_4: Countries GraphQL — Japan info
            Step(
                id="step_4",
                tool_id="countries_graphql",
                input_mapping={"code": "JP"},
                description="Get Japan country info via GraphQL",
                name="Japan Info",
                severity=StepSeverity.NON_CRITICAL,
                validations=[
                    StepValidation(field="country_name", check="not_null", critical=False, message="Country name not available"),
                    StepValidation(field="capital", check="not_null", critical=False, message="Capital not available"),
                ],
            ),
            # step_5: Rick & Morty GraphQL — search studio name as character
            Step(
                id="step_5",
                tool_id="rickmorty_character",
                input_mapping={"name": "step_1.studio_name"},
                description="Search Rick & Morty characters by studio name (fun cross-API test)",
                name="R&M Character",
                severity=StepSeverity.NON_CRITICAL,
                validations=[
                    StepValidation(field="character_name", check="not_null", critical=False, message="R&M character not found"),
                ],
            ),
            # step_6: YouTube REST — search for anime
            Step(
                id="step_6",
                tool_id="youtube_search",
                input_mapping={
                    "q": "$input.anime_name",
                    "part": "snippet",
                    "type": "video",
                    "maxResults": "1",
                },
                description="Search YouTube for anime videos",
                name="YouTube Search",
            ),
            # step_7: YouTube REST — video stats (depends on step_6)
            Step(
                id="step_7",
                tool_id="youtube_video_stats",
                input_mapping={
                    "id": "step_6.video_id",
                    "part": "statistics",
                },
                description="Get YouTube video statistics",
                name="Video Stats",
            ),
            # step_8: GitHub GraphQL QUERY — get repo node ID
            Step(
                id="step_8",
                tool_id="github_graphql_repo",
                input_mapping={
                    "owner": "hrrev",
                    "repo": "workflow-test-sink",
                },
                description="Get repository node ID via GitHub GraphQL",
                name="GitHub Repo ID",
            ),
            # step_9: GitHub GraphQL MUTATION — create issue (fan-in from ALL upstream)
            Step(
                id="step_9",
                tool_id="github_create_anime_report",
                input_mapping={
                    "repo_id": "step_8.repo_node_id",
                    "title": "$input.anime_name",
                    # AniList metadata (step_1)
                    "anime_score": "step_1.score",
                    "anime_episodes": "step_1.episodes",
                    "anime_studio": "step_1.studio_name",
                    "anime_status": "step_1.status",
                    "anime_season": "step_1.season",
                    "anime_season_year": "step_1.season_year",
                    "anime_genres": "step_1.genres",
                    # Sentiment (step_3)
                    "wiki_sentiment": "step_3.sentiment",
                    "wiki_sentiment_score": "step_3.score",
                    # Country info (step_4)
                    "country_name": "step_4.country_name",
                    "country_capital": "step_4.capital",
                    "country_currency": "step_4.currency",
                    "country_continent": "step_4.continent",
                    "country_languages": "step_4.languages",
                    # Rick & Morty (step_5)
                    "rm_character": "step_5.character_name",
                    "rm_species": "step_5.character_species",
                    "rm_status": "step_5.character_status",
                    # YouTube stats (step_7)
                    "youtube_views": "step_7.view_count",
                    "youtube_likes": "step_7.like_count",
                },
                description="Create GitHub issue with full anime intel report via GraphQL mutation",
                name="Create Issue",
            ),
            # step_10: GitHub GraphQL MUTATION — add enrichment comment
            Step(
                id="step_10",
                tool_id="github_add_anime_comment",
                input_mapping={
                    "subject_id": "step_9.issue_id",
                    "wiki_description": "step_2.description",
                    "title_romaji": "step_1.title_romaji",
                    "repo_name": "step_8.repo_name",
                    "repo_stars": "step_8.stars",
                },
                description="Add enrichment comment with Wikipedia description via GraphQL mutation",
                name="Add Comment",
            ),
        ],
        edges=[
            # Level 1 dependencies
            Edge(from_step_id="step_2", to_step_id="step_3"),
            Edge(from_step_id="step_1", to_step_id="step_5"),
            Edge(from_step_id="step_6", to_step_id="step_7"),
            # Fan-in to step_9 (the real aggregation point)
            Edge(from_step_id="step_1", to_step_id="step_9"),
            Edge(from_step_id="step_3", to_step_id="step_9"),
            Edge(from_step_id="step_4", to_step_id="step_9"),
            Edge(from_step_id="step_5", to_step_id="step_9"),
            Edge(from_step_id="step_7", to_step_id="step_9"),
            Edge(from_step_id="step_8", to_step_id="step_9"),
            # Chained mutations
            Edge(from_step_id="step_9", to_step_id="step_10"),
            # step_10 also needs step_2 and step_8 data
            Edge(from_step_id="step_2", to_step_id="step_10"),
            Edge(from_step_id="step_8", to_step_id="step_10"),
        ],
    )


def main():
    tool_configs = {
        "youtube_search": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "youtube_video_stats": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "api_ninjas_sentiment": {"auth_token": os.environ.get("API_NINJAS_KEY", "")},
        "github_graphql_repo": {"auth_token": os.environ.get("GITHUB_PAT", "")},
        "github_create_anime_report": {"auth_token": os.environ.get("GITHUB_PAT", "")},
        "github_add_anime_comment": {"auth_token": os.environ.get("GITHUB_PAT", "")},
    }

    registry = ToolRegistry()
    registry.load_directory("tools")

    if "--register" in sys.argv:
        print(json.dumps(build_workflow().model_dump(), indent=2, default=str))
        return

    workflow = build_workflow()
    anime = input("Anime name (e.g. 'Attack on Titan'): ").strip() or "Attack on Titan"

    print(f"\n=== Running: {workflow.name} for '{anime}' ===\n")

    run = execute(
        workflow,
        {"anime_name": anime},
        registry.get_tool_map(),
        tool_configs,
    )

    print(f"\n=== Run result: {run.status.value} ===")
    for r in run.step_results:
        print(f"\n--- {r.step_id} [{r.status.value}] ---")
        if r.error:
            print(f"  ERROR: {r.error}")
        else:
            print(json.dumps(r.output_data, indent=2, default=str)[:800])


if __name__ == "__main__":
    main()
