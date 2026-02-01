"""
Workflow: Artist Intelligence Briefing (Reduced — no Spotify)

Graph:
    $input.artist_name
       ┌────┬────────┬──────────┐
    step_1  step_2  step_4    step_6
    Wiki    YouTube NewsAPI   Celebrity
    summary search  search    (api ninjas)
       |      |       |
    step_7  step_3  step_5
    Wiki    video   news
    sentiment stats sentiment
       |      |       |         |
       └──────┴───────┴─────────┘
                  |
              step_8: POST briefing

8 steps, 4 APIs + httpbin, fan-out/fan-in, sentiment reused twice.
Best with individual artist names (e.g. "Drake", "Adele") since
the celebrity API requires a person, not a band.

Requires env vars: YOUTUBE_API_KEY, NEWSAPI_KEY, API_NINJAS_KEY
"""

import json
import os
import sys

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.workflow import Edge, Step, StepSeverity, StepValidation, Workflow
from ai_assisted_automation.registry.tool_registry import ToolRegistry


def build_workflow() -> Workflow:
    return Workflow(
        id="artist_intel_reduced",
        name="Artist Intelligence Briefing (Reduced)",
        steps=[
            # step_1: Wikipedia summary (independent)
            Step(
                id="step_1",
                tool_id="wikipedia_summary",
                input_mapping={"title": "$input.artist_name"},
                description="Get Wikipedia summary for the artist",
                name="Wikipedia Bio",
            ),
            # step_2: YouTube search (independent)
            Step(
                id="step_2",
                tool_id="youtube_search",
                input_mapping={
                    "q": "$input.artist_name",
                    "part": "snippet",
                    "type": "video",
                    "maxResults": "1",
                },
                description="Search YouTube for artist's top video",
                name="YouTube Search",
            ),
            # step_3: YouTube video stats (depends on step_2)
            Step(
                id="step_3",
                tool_id="youtube_video_stats",
                input_mapping={
                    "id": "step_2.video_id",
                    "part": "statistics",
                },
                description="Get YouTube video statistics",
                name="Video Stats",
            ),
            # step_4: NewsAPI search (independent)
            Step(
                id="step_4",
                tool_id="newsapi_search",
                input_mapping={
                    "q": "$input.artist_name",
                    "sortBy": "publishedAt",
                    "pageSize": "1",
                },
                description="Search for latest news about the artist",
                name="News Search",
            ),
            # step_5: Sentiment on news headline (depends on step_4)
            Step(
                id="step_5",
                tool_id="api_ninjas_sentiment",
                input_mapping={"text": "step_4.headline"},
                description="Analyze sentiment of news headline",
                name="News Sentiment",
            ),
            # step_6: Celebrity info (independent)
            Step(
                id="step_6",
                tool_id="api_ninjas_celebrity",
                input_mapping={"name": "$input.artist_name"},
                description="Look up celebrity info (age, nationality, net worth)",
                name="Celebrity Info",
                severity=StepSeverity.NON_CRITICAL,
                validations=[
                    StepValidation(field="nationality", check="not_null", critical=False, message="Nationality not available"),
                    StepValidation(field="net_worth", check="not_null", critical=False, message="Net worth not available"),
                    StepValidation(field="age", check="not_null", critical=False, message="Age not available"),
                ],
            ),
            # step_7: Sentiment on Wikipedia summary (depends on step_1)
            Step(
                id="step_7",
                tool_id="api_ninjas_sentiment",
                input_mapping={"text": "step_1.summary"},
                description="Analyze sentiment of Wikipedia bio summary",
                name="Bio Sentiment",
            ),
            # step_8: POST compiled briefing (fan-in from all branches)
            Step(
                id="step_8",
                tool_id="httpbin_post",
                input_mapping={
                    "artist_name": "$input.artist_name",
                    "wikipedia_summary": "step_1.summary",
                    "wikipedia_description": "step_1.description",
                    "youtube_video_title": "step_2.video_title",
                    "youtube_views": "step_3.view_count",
                    "youtube_likes": "step_3.like_count",
                    "news_headline": "step_4.headline",
                    "news_source": "step_4.source",
                    "news_sentiment": "step_5.sentiment",
                    "news_sentiment_score": "step_5.score",
                    "bio_sentiment": "step_7.sentiment",
                    "bio_sentiment_score": "step_7.score",
                    "celebrity_nationality": "step_6.nationality",
                    "celebrity_net_worth": "step_6.net_worth",
                    "celebrity_age": "step_6.age",
                },
                description="POST compiled artist intelligence briefing",
                name="Compile Briefing",
            ),
        ],
        edges=[
            Edge(from_step_id="step_2", to_step_id="step_3"),
            Edge(from_step_id="step_4", to_step_id="step_5"),
            Edge(from_step_id="step_1", to_step_id="step_7"),
            # fan-in to step_8
            Edge(from_step_id="step_1", to_step_id="step_8"),
            Edge(from_step_id="step_3", to_step_id="step_8"),
            Edge(from_step_id="step_5", to_step_id="step_8"),
            Edge(from_step_id="step_6", to_step_id="step_8"),
            Edge(from_step_id="step_7", to_step_id="step_8"),
        ],
    )


def main():
    tool_configs = {
        "youtube_search": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "youtube_video_stats": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "newsapi_search": {"auth_token": os.environ.get("NEWSAPI_KEY", "")},
        "api_ninjas_sentiment": {"auth_token": os.environ.get("API_NINJAS_KEY", "")},
        "api_ninjas_celebrity": {"auth_token": os.environ.get("API_NINJAS_KEY", "")},
    }

    registry = ToolRegistry()
    registry.load_directory("tools")

    if "--register" in sys.argv:
        print(json.dumps(build_workflow().model_dump(), indent=2, default=str))
        return

    workflow = build_workflow()
    artist = input("Artist name (e.g. 'Drake'): ").strip() or "Drake"

    print(f"\n=== Running: {workflow.name} for '{artist}' ===\n")

    run = execute(
        workflow,
        {"artist_name": artist},
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
