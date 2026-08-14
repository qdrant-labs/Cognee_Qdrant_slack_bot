"""Slack Bolt Socket Mode entrypoint for CVlizer."""

import asyncio
import os
import re
import sys
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

import cvlizer.config  # ensures adapter registration and env loading
from cvlizer.matcher import match_job
from cvlizer.blocks import (
    create_help_block,
    create_loading_block,
    create_match_results_block,
)

# Initialize Slack Bolt Async App
bot_token = os.getenv("SLACK_BOT_TOKEN") or "xoxb-dummy-token-for-init"
app_token = os.getenv("SLACK_APP_TOKEN") or "xapp-dummy-token-for-init"

app = AsyncApp(token=bot_token)


def clean_mention_text(text: str) -> str:
    """Strips bot user tags <@U12345> and leading/trailing whitespace."""
    cleaned = re.sub(r"<@[A-Z0-9]+>", "", text)
    return cleaned.strip()


async def process_job_match_task(client, channel_id: str, thread_ts: str, text: str, loading_ts: str):
    """Background worker for matching a job description and posting results."""
    try:
        # Run the full matching pipeline
        result = await match_job(text, index_job=True)
        blocks = create_match_results_block(result)

        # Post top-3 results in thread
        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Top candidates found for your role!",
            blocks=blocks,
        )

        # Update initial loading message
        await client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            text="✅ Job indexed and candidate matches generated below.",
            blocks=[
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "✅ *Job indexed in Cognee & matched against candidate graph.*",
                        }
                    ],
                }
            ],
        )

    except Exception as e:
        print(f"Error during job matching task: {e}")
        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"⚠️ An error occurred while searching candidate graph: `{str(e)}`",
        )


@app.event("app_mention")
async def handle_app_mention(event, say, client):
    """
    Handles @CVlizer mentions in Slack channels.
    Acks immediately (<3s) to prevent timeouts, posts a thread placeholder,
    and runs the Cognee match pipeline asynchronously.
    """
    raw_text = event.get("text", "")
    channel_id = event.get("channel")
    event_ts = event.get("ts")
    thread_ts = event.get("thread_ts", event_ts)

    cleaned = clean_mention_text(raw_text)

    # 1. Handle help command or empty mention
    if not cleaned or cleaned.lower().startswith("help"):
        await say(
            channel=channel_id,
            thread_ts=thread_ts,
            blocks=create_help_block(),
            text="CVlizer Help",
        )
        return

    # 2. Post immediate loading acknowledgment in thread
    loading_res = await client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        blocks=create_loading_block(cleaned),
        text="Analyzing job description and finding candidate matches...",
    )
    loading_ts = loading_res["ts"]

    # 3. Spawn asynchronous background task for Cognee indexing & search
    asyncio.create_task(
        process_job_match_task(
            client=client,
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=cleaned,
            loading_ts=loading_ts,
        )
    )


async def main():
    if not bot_token or not app_token:
        print("Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN are required.")
        sys.exit(1)

    handler = AsyncSocketModeHandler(app, app_token)
    print("🚀 CVlizer Slack App is starting in Socket Mode...")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
