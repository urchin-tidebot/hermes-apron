import pytest
from hermes_apron.media import write_target
from hermes_apron.transport import ProtocolError


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/write/" + "a" * 32,
        "https://evil.example/write/" + "a" * 32,
        "https://user:pass@chat.example/write/" + "a" * 32,
        "https://chat.example/write/../files/" + "a" * 32,
        "https://chat.example/write/" + "a" * 32 + "?token=secret",
        "file:///etc/hosts",
    ],
)
def test_capability_target_never_trusts_message_supplied_urls(url):
    with pytest.raises(ProtocolError):
        write_target("https://chat.example", url)
