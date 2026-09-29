from __future__ import annotations

import json
import math
import mimetypes
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from backend import compress_text, decompress_bits, serialize_huffman_tree
from channel import channel_decode_detailed, channel_encode, inject_channel_noise
from metrics import (
    calculate_avg_code_length,
    calculate_ber,
    calculate_efficiency,
    calculate_entropy,
)

WEB_ROOT = Path(__file__).resolve().parent / "web"
MAX_TEXT_LENGTH = 10_000


def _character_label(character: str) -> str:
    return {" ": "SPACE", "\n": "LF", "\r": "CR", "\t": "TAB"}.get(character, character)


def simulate(payload: dict) -> dict:
    text = payload.get("text", "")
    if not isinstance(text, str):
        raise ValueError("Source text must be a string.")
    if not text:
        raise ValueError("Enter a message to send through the pipeline.")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Keep the message under {MAX_TEXT_LENGTH:,} characters.")
    if not text.isascii():
        raise ValueError("This demonstration uses 8-bit ASCII. Please remove non-ASCII characters.")

    try:
        noise_percent = float(payload.get("noise_percent", 0))
    except (TypeError, ValueError):
        raise ValueError("Noise rate must be a number.") from None
    if not math.isfinite(noise_percent) or not 0 <= noise_percent <= 10:
        raise ValueError("Noise rate must be between 0% and 10%.")

    compressed_bits, huffman_codes, tree_root, original_size_bits = compress_text(text)
    encoded_stream, padding = channel_encode(compressed_bits)
    noisy_stream = inject_channel_noise(encoded_stream, noise_percent)

    forced_error_bit = payload.get("forced_error_bit")
    if forced_error_bit is not None:
        if not isinstance(forced_error_bit, int) or isinstance(forced_error_bit, bool):
            raise ValueError("Choose a valid transmitted bit position.")
        if not 1 <= forced_error_bit <= len(noisy_stream):
            raise ValueError(f"Choose a bit position from 1 to {len(noisy_stream)}.")
        index = forced_error_bit - 1
        noisy_stream = (
            noisy_stream[:index]
            + ("1" if encoded_stream[index] == "0" else "0")
            + noisy_stream[index + 1 :]
        )

    received_ber = calculate_ber(encoded_stream, noisy_stream)
    channel_result = channel_decode_detailed(noisy_stream, padding)
    recovered_bits = channel_result["recovered_bits"]
    corrected_blocks = channel_result["corrected_blocks"]
    reconstructed_text = decompress_bits(recovered_bits, tree_root)

    counts = Counter(text)
    codebook = [
        {
            "character": _character_label(character),
            "frequency": counts[character],
            "code": code,
            "length": len(code),
        }
        for character, code in sorted(huffman_codes.items())
    ]

    padded_source = compressed_bits + ("0" * padding)
    blocks = []
    for index in range(0, len(encoded_stream), 7):
        block_number = index // 7
        transmitted = encoded_stream[index : index + 7]
        received = noisy_stream[index : index + 7]
        decoded = channel_result["blocks"][block_number]
        changed_positions = [
            position + 1
            for position, (sent_bit, received_bit) in enumerate(zip(transmitted, received))
            if sent_bit != received_bit
        ]
        blocks.append(
            {
                "number": block_number + 1,
                "source": padded_source[block_number * 4 : block_number * 4 + 4],
                "transmitted": transmitted,
                "received": received,
                "corrected_codeword": decoded["corrected_codeword"],
                "data_bits": decoded["data_bits"],
                "syndrome": decoded["syndrome"],
                "syndrome_value": decoded["syndrome_value"],
                "error_position": decoded["error_position"],
                "changed_positions": changed_positions,
                "corrected": decoded["corrected"],
            }
        )

    return {
        "source_text": text,
        "reconstructed_text": reconstructed_text,
        "matches": text == reconstructed_text,
        "ascii": [{"character": _character_label(character), "binary": f"{ord(character):08b}"} for character in text[:80]],
        "ascii_truncated": len(text) > 80,
        "ascii_bits": "".join(f"{ord(character):08b}" for character in text),
        "compressed_bits": compressed_bits,
        "padded_bits": padded_source,
        "padding": padding,
        "huffman_tree": serialize_huffman_tree(tree_root),
        "transmitted_bits": encoded_stream,
        "received_bits": noisy_stream,
        "recovered_bits": recovered_bits,
        "forced_error_bit": forced_error_bit,
        "codebook": codebook,
        "blocks": blocks,
        "metrics": {
            "entropy": calculate_entropy(text),
            "average_code_length": calculate_avg_code_length(huffman_codes, text),
            "efficiency": calculate_efficiency(
                calculate_entropy(text), calculate_avg_code_length(huffman_codes, text)
            ),
            "original_bits": original_size_bits,
            "compressed_bits": len(compressed_bits),
            "channel_bits": len(encoded_stream),
            "compression_percent": round(
                (1 - len(compressed_bits) / original_size_bits) * 100, 2
            ) if original_size_bits else 0,
            "channel_ber": received_ber,
            "corrected_blocks": corrected_blocks,
            "total_blocks": len(blocks),
        },
    }


class PipelineHandler(BaseHTTPRequestHandler):
    server_version = "SignalLab/1.0"

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json({"status": "ok"})
            return

        filename = "index.html" if path == "/" else path.lstrip("/")
        if filename not in {"index.html", "styles.css", "app.js"}:
            self.send_error(404)
            return

        try:
            body = (WEB_ROOT / filename).read_bytes()
        except OSError:
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/simulate":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= 1_000_000:
                raise ValueError("Request body is empty or too large.")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            self._send_json(simulate(payload))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"error": "Request body must contain valid JSON."}, 400)
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    host = "127.0.0.1"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer((host, port), PipelineHandler)
    print(f"Signal Lab is running at http://{host}:{port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
