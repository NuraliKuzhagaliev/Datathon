# Local model candidate

- Official publisher/repository: `Qwen/Qwen3-VL-2B-Instruct`.
- Pinned revision: `89644892e4d85e24eaac8bacfd4f463576704203`.
- Model card: https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct
- Declared license: Apache-2.0 (official model card). No model license is inferred for unrelated third-party checkpoints.
- Weight file: `model.safetensors`, 4,255,140,312 bytes; official LFS SHA-256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`.
- Adapter: PyTorch/Transformers, local files only, SDPA, BF16 only where CUDA reports support, otherwise FP16. No remote code is trusted.
- Intended use: assistive review of visible actions under explicitly enabled registry predicates, with raw source evidence and human review. No automated personnel/legal decision.
- Out of scope: identity or face embeddings, intent/permission inference, audio, accounting/ledger correctness, arbitrary unknown legal categories, compliance certification.

Provisioning verifies checksums and writes `models/.../cashproof-manifest.json`. A portable release must include that complete directory and notices. The current download/compatibility status and any measured hardware results belong in `docs/integration/verification.md`; a model-card capability is not a benchmark on this dataset.
