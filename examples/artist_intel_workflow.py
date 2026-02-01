"""
Workflow: Artist Intelligence Briefing

Graph:
    $input.artist_name
            |
       step_1: Spotify token exchange
            |
       step_2: Spotify search artist
            |
   ┌────┬───┴───┬──────────┐
step_3  step_4  step_6   step_8      step_5 (independent)
top     related YouTube  NewsAPI     Wikipedia summary
tracks  artists search   search
   │    │        │         │
   │    │     step_7    step_9
   │    │     video     sentiment
   │    │     stats     analysis
   │    │        │         │
   └────┴────────┴─────────┴──── step_5 ──┐
                                           │
                                    step_10: POST briefing

11 steps, 6 APIs, fan-out from step_2, fan-in at step_10.

Requires env vars:
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
  YOUTUBE_API_KEY, NEWSAPI_KEY, API_NINJAS_KEY
"""

import json
import os
import sys

from ai_assisted_automation.executor.workflow_executor import execute
from ai_assisted_automation.models.workflow import Edge, Step, Workflow
from ai_assisted_automation.registry.tool_registry import ToolRegistry


def build_workflow() -> Workflow:
    return Workflow(
        id="artist_intel",
        name="Artist Intelligence Briefing",
        steps=[
            # Step 1: Get Spotify access token
            Step(
                id="step_1",
                tool_id="spotify_token",
                input_mapping={},
                description="Exchange Spotify client credentials for access token",
            ),
            # Step 2: Search for artist on Spotify
            Step(
                id="step_2",
                tool_id="spotify_search_artist",
                input_mapping={
                    "access_token": "step_1.access_token",
                    "q": "$input.artist_name",
                    "type": "artist",
                    "limit": "1",
                },
                description="Search Spotify for the artist",
            ),
            # Step 3: Get top tracks
            Step(
                id="step_3",
                tool_id="spotify_top_tracks",
                input_mapping={
                    "access_token": "step_1.access_token",
                    "artist_id": "step_2.artist_id",
                    "market": "US",
                },
                description="Get artist's top tracks on Spotify",
            ),
            # Step 4: Get related artists
            Step(
                id="step_4",
                tool_id="spotify_related_artists",
                input_mapping={
                    "access_token": "step_1.access_token",
                    "artist_id": "step_2.artist_id",
                },
                description="Get related artists from Spotify",
            ),
            # Step 5: Wikipedia summary (independent — only needs $input)
            Step(
                id="step_5",
                tool_id="wikipedia_summary",
                input_mapping={
                    "title": "$input.artist_name",
                },
                description="Get Wikipedia summary for the artist",
            ),
            # Step 6: YouTube search for music video
            Step(
                id="step_6",
                tool_id="youtube_search",
                input_mapping={
                    "q": "$input.artist_name",
                    "part": "snippet",
                    "type": "video",
                    "maxResults": "1",
                },
                description="Search YouTube for artist's music video",
            ),
            # Step 7: YouTube video stats
            Step(
                id="step_7",
                tool_id="youtube_video_stats",
                input_mapping={
                    "id": "step_6.video_id",
                    "part": "statistics",
                },
                description="Get YouTube video statistics",
            ),
            # Step 8: News search
            Step(
                id="step_8",
                tool_id="newsapi_search",
                input_mapping={
                    "q": "$input.artist_name",
                    "sortBy": "publishedAt",
                    "pageSize": "1",
                },
                description="Search for latest news about the artist",
            ),
            # Step 9: Sentiment analysis on headline
            Step(
                id="step_9",
                tool_id="api_ninjas_sentiment",
                input_mapping={
                    "text": "step_8.headline",
                },
                description="Analyze sentiment of news headline",
            ),
            # Step 10: POST compiled briefing to httpbin
            Step(
                id="step_10",
                tool_id="httpbin_post",
                input_mapping={
                    "artist_name": "step_2.name",
                    "genres": "step_2.genres",
                    "popularity": "step_2.popularity",
                    "top_track": "step_3.track_1",
                    "related_artist": "step_4.related_1",
                    "wikipedia_summary": "step_5.summary",
                    "youtube_video": "step_6.video_title",
                    "youtube_views": "step_7.view_count",
                    "news_headline": "step_8.headline",
                    "news_sentiment": "step_9.sentiment",
                },
                description="POST compiled artist intelligence briefing",
            ),
        ],
        edges=[
            Edge(from_step_id="step_1", to_step_id="step_2"),
            Edge(from_step_id="step_2", to_step_id="step_3"),
            Edge(from_step_id="step_2", to_step_id="step_4"),
            Edge(from_step_id="step_2", to_step_id="step_6"),
            Edge(from_step_id="step_2", to_step_id="step_8"),
            Edge(from_step_id="step_6", to_step_id="step_7"),
            Edge(from_step_id="step_8", to_step_id="step_9"),
            Edge(from_step_id="step_3", to_step_id="step_10"),
            Edge(from_step_id="step_4", to_step_id="step_10"),
            Edge(from_step_id="step_5", to_step_id="step_10"),
            Edge(from_step_id="step_7", to_step_id="step_10"),
            Edge(from_step_id="step_9", to_step_id="step_10"),
        ],
    )


def main():
    registry = ToolRegistry()
    registry.load_directory("tools")

    tool_configs = {
        "spotify_token": {
            "auth_username": os.environ.get("SPOTIFY_CLIENT_ID", ""),
            "auth_token": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
        },
        "youtube_search": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "youtube_video_stats": {"auth_token": os.environ.get("YOUTUBE_API_KEY", "")},
        "newsapi_search": {"auth_token": os.environ.get("NEWSAPI_KEY", "")},
        "api_ninjas_sentiment": {"auth_token": os.environ.get("API_NINJAS_KEY", "")},
    }

    if "--register" in sys.argv:
        workflow = build_workflow()
        print(json.dumps(workflow.model_dump(), indent=2, default=str))
        return

    workflow = build_workflow()
    artist = input("Artist name (e.g. 'Radiohead'): ").strip() or "Radiohead"

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
            print(json.dumps(r.output_data, indent=2, default=str)[:600])


if __name__ == "__main__":
    main()
