from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time

import pytest

from cashproof import media
from cashproof.errors import ProcessingError


def test_uploaded_playlist_and_network_protocol_never_contact_a_server(tmp_path):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/generated-segment.ts"
        disguised = tmp_path / "synthetic-playlist.mov"
        disguised.write_text(
            "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\n"
            + url
            + "\n#EXT-X-ENDLIST\n",
            encoding="ascii",
        )
        with pytest.raises(ProcessingError):
            media.validate_container(disguised)
        with pytest.raises(ProcessingError):
            media.run(["-i", url, "-f", "null", "-"], time.time() + 10)
        assert requests == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
