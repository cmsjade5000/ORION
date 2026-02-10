from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscordContext:
    """
    Minimal Discord routing context used to derive a stable conversation key.

    - DMs: guild_id is None; user_id is required.
    - Guild channels/threads: guild_id is required; user_id is optional (shared context).
    """

    channel_id: str
    user_id: str | None = None
    guild_id: str | None = None
    thread_id: str | None = None


def conversation_key(ctx: DiscordContext) -> str:
    """
    Stable conversation key used for routing + session identity.

    Design:
    - DMs are per-user: include DM channel id + user id
    - Guild channels are shared: include guild id + channel id
    - Threads scope tasks: include thread id when present
    """

    if ctx.guild_id is None:
        if not ctx.user_id:
            raise ValueError("DM context requires user_id")
        return f"discord:dm:channel:{ctx.channel_id}:user:{ctx.user_id}"

    thread = ctx.thread_id or "-"
    return f"discord:guild:{ctx.guild_id}:channel:{ctx.channel_id}:thread:{thread}"


def openclaw_target(ctx: DiscordContext) -> str:
    """
    Convert routing context to an OpenClaw Discord messaging target.

    - DMs: user:<id>
    - Guild channels: channel:<channel_id>
    - Threads: channel:<thread_id> (Discord threads are channels)
    """

    if ctx.guild_id is None:
        if not ctx.user_id:
            raise ValueError("DM context requires user_id")
        return f"user:{ctx.user_id}"

    return f"channel:{ctx.thread_id or ctx.channel_id}"

