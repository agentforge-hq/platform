"""Prepare, serve, and finalize a private relevance review worksheet."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.core import EvaluationError, load_corpus, load_json
from evaluation.review import make_packet, render_packet, write_successor


def serve(path: Path, port: int) -> None:
    if path.stat().st_size > 20_000_000:
        raise EvaluationError('The worksheet exceeds the 20 MB serving limit.')
    content = path.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != '/':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

    with ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        print(
            json.dumps({'url': f'http://127.0.0.1:{server.server_port}/', 'scope': 'one local worksheet only'}),
            flush=True,
        )
        server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ['prepare', 'finalize']:
        sub = commands.add_parser(command)
        sub.add_argument('--corpus', type=Path, default=Path(__file__).resolve().parents[1] / 'evaluation')
        sub.add_argument('--catalog', type=Path, required=True)
        sub.add_argument('--output', type=Path, required=True)
        if command == 'finalize':
            sub.add_argument('--annotations', type=Path, required=True)
        else:
            sub.add_argument(
                '--demo', action='store_true', help='Use separate synthetic interface tasks, not held-out tasks.'
            )
    preview = commands.add_parser('serve')
    preview.add_argument('worksheet', type=Path)
    preview.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'serve':
        if not 0 <= args.port <= 65535:
            parser.error('Use a port between 0 and 65535; zero selects an available port.')
        serve(args.worksheet, args.port)
        return
    packet = make_packet(args.corpus, args.catalog)
    if args.command == 'prepare':
        if args.demo:
            demo = Path(__file__).resolve().parents[1] / 'evaluation/review-demo.json'
            load_corpus(args.corpus, development=demo)
            packet.update(prompts=load_json(demo)['prompts'], packet_id='demo-' + packet['packet_id'], demo=True)
        page = render_packet(packet)
        with args.output.open('x', encoding='utf-8') as output:
            output.write(page)
        result = {
            'worksheet': str(args.output),
            'tasks': len(packet['prompts']),
            'skills': len(packet['skills']),
            'catalog_revision': packet['catalog_revision'],
            'human_review_status': 'demo_only' if args.demo else 'pending',
        }
    else:
        freeze = write_successor(packet, load_json(args.annotations), args.output)
        result = {
            'corpus': str(args.output),
            'corpus_sha256': freeze['corpus_sha256'],
            'human_review_status': freeze['human_review_status'],
            'release_gates_established': False,
        }
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except (EvaluationError, OSError, ValueError, KeyError, TypeError) as error:
        detail = (
            str(error) if isinstance(error, EvaluationError) else 'Check the input files and use a new output path.'
        )
        print(f'Review could not complete ({type(error).__name__}): {detail}', file=sys.stderr)
        raise SystemExit(1)
