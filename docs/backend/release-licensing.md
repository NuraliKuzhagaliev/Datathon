# Portable release notice inventory

The private 0.3.1 candidate remains immutable and is not approved for public binary redistribution. Its existing ZIP/checksum and measured runtime evidence remain valid. A read-only audit of its manifest, Python distribution metadata and notice files found 57 installed distributions matching all 57 inventory records, 181 checked files and zero missing/changed manifest hashes. Python's license, FFmpeg GPL text/build README/provenance, package metadata and recorded license files are present.

The pinned model card declares Apache-2.0, but the candidate model folder has no standalone license text. Tokenizers 0.22.2 declares the Apache classifier but its wheel inventory records no license/notice file. These are notice completeness findings; they do not mean the components are prohibited or that the other packages are fully reviewed.

## Prepared correction for subsequent bundles

`assets/licenses/provenance.json` pins two supplemental texts to exact applicable components:

| Component | Applicable version | Upstream text | SHA-256 |
| --- | --- | --- | --- |
| Qwen/Qwen3-VL-2B-Instruct | 89644892e4d85e24eaac8bacfd4f463576704203 | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.txt) | cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 |
| tokenizers | 0.22.2, upstream f383101a26663708484cac0727792aad74f78234 | [Pinned upstream LICENSE](https://github.com/huggingface/tokenizers/blob/f383101a26663708484cac0727792aad74f78234/LICENSE) | c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4 |

Model declaration: [official pinned model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/README.md). The generic Apache text is separately identified, not represented as a file from the model repository. No upstream notice is invented or removed.

The builder copies matching supplemental texts into `licenses/supplemental`, verifies size/SHA-256 and includes their provenance in the new bundle manifest. Mismatched versions are excluded. A direct functional check using the actual pinned model/package inventory verified both copied hashes, wrong-version exclusion, rejection of a changed license hash and rejection of parent traversal. The original release was not rewritten. A separate 8,778-byte `RELEASE-LICENSE-SUPPLEMENT.zip` in the parent task outputs contains the two texts and provenance; it passed full CRC verification. Ship this as an explicitly separate notice supplement for private review, without changing the trusted old ZIP.

Audit from the repository:

```powershell
../../work/.venv/Scripts/python.exe tools/audit_release_licenses.py --bundle releases/backend --receipt ../../outputs/new-release-license-inventory.json
```

Use a new receipt path. The audit does not execute bundled packages, mutate the release, grant licensing approval or change a `public_redistribution_reviewed` flag.

## Remaining release work

The [vendor identifies these Windows FFmpeg builds as static GPLv3](https://www.gyan.dev/ffmpeg/builds/); the actual binary enables GPL/version3, libx264 and other external libraries. A source revision URL and GPL text do not provide the exact corresponding source/build inputs for this entire static binary. Obtain and package the exact FFmpeg/external-library sources, modifications and build instructions under the applicable terms, or qualify a replacement with a complete compliant distribution. Do not describe this GPL executable as an LGPL-only build. The [official FFmpeg licensing page](https://ffmpeg.org/legal.html) explains the distinction and source correspondence.

PyAV's Python package BSD declaration does not by itself cover every embedded native FFmpeg library. Torch/CUDA and other bundled native dependency terms/notices also require component-level review. B's Electron/JavaScript packages and displayed notices need their own distribution inventory. An application source license must be chosen and documented by the owner before public source/binary licensing claims. These items remain open; the notice supplement closes two specific missing-text findings only. No public binary or private dataset has been uploaded.
