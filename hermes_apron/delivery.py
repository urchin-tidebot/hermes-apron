"""Send-only connections coexist with the live consumer; no consumer lock or inbox mutation."""

import asyncio
from gateway.platforms._shared import extra_or_secret
from .config import Options, read_secret
from .transport import Transport, ProtocolError


async def standalone_sender(
    config, chat_id, message, *, thread_id=None, media_files=None, force_document=False
):
    transport = None
    try:
        options = Options.load(config)
        room = thread_id or chat_id or extra_or_secret(config.extra, "home_room", "APRON_HOME_ROOM")
        if (
            room not in options.rooms
            or media_files
            or not isinstance(message, str)
            or not 0 < len(message.encode()) <= 65536
        ):
            raise ValueError()
        token = await asyncio.to_thread(read_secret, options.token_file)
        transport = Transport(
            options.endpoint, options.url, token, test_loopback=options.test_loopback
        )
        await transport.connect()
        if "rooms" in transport.capabilities:
            joined = await transport.call("room_list", {"filter": "joined"})
            rooms = {r["room_id"]: r for r in joined.get("joined", [])}
            if room not in rooms or (
                thread_id and chat_id and rooms[room].get("parent_room_id") != chat_id
            ):
                raise ValueError()
        elif room != "general":
            raise ValueError()
        result = await transport.call(
            "message", {"room_id": room, "body": {"text": message, "format": "markdown"}}
        )
        if not result.get("message_id"):
            raise ProtocolError("Apron did not confirm delivery")
        return {"success": True, "message_id": result["message_id"]}
    except ValueError, OSError, ProtocolError:
        return {"error": "Apron standalone delivery failed or destination denied"}
    finally:
        if transport:
            await transport.close()
