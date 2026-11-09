"""Validate fields used from untrusted Apron frames before indexing or storing them."""


class ProtocolError(Exception):
    pass


class InvalidFrame(ProtocolError):
    """Malformed peer data is terminal until an explicit lifecycle restart."""


def scalar_text(value):
    if not isinstance(value, str):
        raise InvalidFrame("invalid Apron text")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise InvalidFrame("invalid Apron Unicode text") from None
    return value


def scalar_strings(value):
    """Check all JSON strings, including keys and unconsumed response fields."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            scalar_text(item)
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def record(value):
    if not isinstance(value, dict):
        raise InvalidFrame("invalid Apron object")
    return value


def records(value):
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise InvalidFrame("invalid Apron record list")
    return value


def identifier(value):
    scalar_text(value)
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise InvalidFrame("invalid Apron identifier")
    return value


def position(value):
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or len(value) > 19
        or int(value) > 2**63 - 1
    ):
        raise InvalidFrame("invalid Apron log position")
    return value


def string_list(value):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InvalidFrame("invalid Apron string list")
    for item in value:
        scalar_text(item)
    return value


def room_records(value, *, history=False):
    values = records(value)
    for room in values:
        identifier(room.get("room_id"))
        if "title" in room:
            scalar_text(room["title"])
        if "parent_room_id" in room:
            identifier(room["parent_room_id"])
        if history or "latest_log_id" in room:
            position(room.get("latest_log_id"))
    return values


def message_record(value, *, history=False):
    message = record(value)
    if history or "room_id" in message:
        identifier(message.get("room_id"))
    sender = record(message.get("from"))
    identifier(sender.get("user_id"))
    if "name" in sender:
        scalar_text(sender["name"])
    string_list(sender.get("roles", []))
    body = record(message.get("body", {}))
    scalar_text(body.get("text", ""))
    string_list(body.get("mentions", []))
    if "reply_to" in message:
        identifier(record(message["reply_to"]).get("message_id"))
    if "deleted" in message and not isinstance(message["deleted"], bool):
        raise InvalidFrame("invalid Apron deletion flag")
    for key in ("message_id", "log_id", "prev_log_id"):
        if key in message or (history and key != "prev_log_id"):
            (position if key.endswith("log_id") else identifier)(message.get(key))
    return message


def delivery_receipt(value, *, writer=False):
    result = record(value)
    identifier(result.get("message_id"))
    if writer:
        embeds = records(result.get("embeds"))
        if (
            len(embeds) != 1
            or not isinstance(embeds[0].get("write_url"), str)
            or not embeds[0]["write_url"]
        ):
            raise InvalidFrame("invalid Apron writer receipt")
        scalar_text(embeds[0]["write_url"])
    return result
