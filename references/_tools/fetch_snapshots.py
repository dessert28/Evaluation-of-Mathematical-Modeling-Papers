"""Collect immutable, inactive text snapshots; never import upstream code."""
import concurrent.futures
import datetime
import hashlib
import io
import json
import pathlib
import subprocess
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPOS = [
    'yohanchen1/MathModelingAgent',
    'YiFraternity/LLM-MM-Agent',
    'ngstcf/agentic-paper-review',
    'pavelgolikov/arxiv-research-agent',
    'khoj-ai/openpaper',
    'zhnnky329/MathModeling-skills',
    'ShaishavMaisuria/research-paper-lifecycle-skills',
    'erezweinstein5/eval-layer',
    'Y-love-han/math-modeling-skill',
    'chengziyue1222/math-model-agent',
]
SUFFIXES = {'.md', '.py', '.json', '.yaml', '.yml', '.toml', '.txt', '.ts',
            '.tsx', '.js', '.sh', '.html', '.css', '.mmd', '.rst'}
EXCLUDED = {'node_modules', '.git', '.venv', '__pycache__', 'data', 'datasets'}
STAMP = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def collect(repo):
    info = {'repository': repo, 'url': 'https://github.com/' + repo,
            'retrieved_at': STAMP, 'activation': 'reference_only', 'files': []}
    try:
        result = subprocess.run(
            ['git', '-c', 'credential.helper=', 'ls-remote', '--symref', info['url'] + '.git', 'HEAD'],
            capture_output=True, text=True, timeout=50, check=True)
        lines = result.stdout.splitlines()
        info['default_branch'] = next(x.split()[1].removeprefix('refs/heads/') for x in lines if x.startswith('ref:'))
        sha = next(x.split()[0] for x in lines if not x.startswith('ref:') and x.endswith('HEAD'))
        info['commit'] = sha
        url = 'https://codeload.github.com/' + repo + '/zip/' + sha
        req = urllib.request.Request(url, headers={'User-Agent': 'paper-review-reference-audit'})
        with urllib.request.urlopen(req, timeout=90) as response:
            archive = response.read(100 * 1024 * 1024 + 1)
        if len(archive) > 100 * 1024 * 1024:
            raise ValueError('archive exceeds 100 MB cap')
        info['archive_sha256'] = hashlib.sha256(archive).hexdigest()
        destination = ROOT / 'references' / 'upstream' / repo.replace('/', '--')
        destination.mkdir(parents=True, exist_ok=True)
        skipped = 0
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            for item in z.infolist():
                rel = pathlib.PurePosixPath(*pathlib.PurePosixPath(item.filename).parts[1:])
                if item.is_dir() or not rel.parts:
                    continue
                if '..' in rel.parts or rel.is_absolute() or any(':' in p for p in rel.parts):
                    raise ValueError('unsafe archive member')
                is_license = rel.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE'))
                if (set(rel.parts) & EXCLUDED or item.file_size > 2 * 1024 * 1024
                    or rel.name.startswith('.env') or rel.name in {'package-lock.json', 'uv.lock'}
                    or (rel.suffix.lower() not in SUFFIXES and not is_license)):
                    skipped += 1
                    continue
                # OpenPaper is large: retain evaluation/code references, not its frontend.
                if repo == 'khoj-ai/openpaper' and len(rel.parts) > 1 and rel.parts[0] not in {'server', 'docs'}:
                    skipped += 1
                    continue
                content = z.read(item)
                target = destination.joinpath(*rel.parts)
                if target.exists() and target.read_bytes() != content:
                    raise ValueError('existing snapshot differs; refusing to overwrite: ' + str(rel))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                info['files'].append({'path': rel.as_posix(), 'bytes': len(content),
                                      'sha256': hashlib.sha256(content).hexdigest()})
        info['skipped_files'] = skipped
        info['status'] = 'downloaded'
        info['license_files'] = [f['path'] for f in info['files']
                                 if pathlib.PurePosixPath(f['path']).name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE'))]
        (destination / 'SOURCE_MANIFEST.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        print(repo + ': downloaded ' + str(len(info['files'])) + ' files @ ' + sha[:12], flush=True)
    except Exception as exc:
        info['status'] = 'failed'
        info['error'] = type(exc).__name__ + ': ' + str(exc)
        print(repo + ': FAILED ' + info['error'], flush=True)
    return info


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(collect, REPOS))
    (ROOT / 'references' / 'SOURCES.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(1 if any(x['status'] != 'downloaded' for x in results) else 0)
