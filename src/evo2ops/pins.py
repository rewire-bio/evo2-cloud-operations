"""Every external artefact the GPU job loads, pinned by revision and SHA-256."""

WEIGHTS = {
    "evo2_7b": {
        "repo_id": "arcinstitute/evo2_7b",
        "revision": "bda0089f92582d5baabf0f22d9fc85f3588f6b58",
        "filename": "evo2_7b.pt",
        "sha256": "c66645929dc1b9c631f5be656da8726f38946315dc9167000a615dd626fcecf4",
        "size": 13766621200,
    },
    "evo2_7b_base": {
        "repo_id": "arcinstitute/evo2_7b_base",
        "revision": "074097e9dc788e8bfe045d6495b9f6153a7c6bfc",
        "filename": "evo2_7b_base.pt",
        "sha256": "d8a0e775a5d849921b8725837c6a3cbc71fa15e712f4189a2ed52ef955aad29b",
        "size": 13006429947,
    },
}

EXON_CLASSIFIER = {
    "repo_id": "schmojo/evo2-exon-classifier",
    "revision": "3ce7ccd4708aedce3d4ce58f21e30d894b75ad3c",
    "filename": "model.safetensors",
    "sha256": "0394fdbf4f533a280a41357d795df29a53a9d26444cfa2ab1bb670b8161ae191",
    # From the pinned config.json: Linear(8192, 1024), ReLU, Linear(1024, 1), sigmoid.
    "embedding_dim": 8192,
    "hidden_dim": 1024,
}

# Arc's expected forward-pass loss for evo2_7b in evo2/test/test_evo2.py at commit 53f1959.
W0_EXPECTED_LOSS = 0.3476563
W0_TOLERANCE = 1e-3

BRCA1_WINDOW = 8192
EXON_LAYER = "blocks.26"
PROBE_LENGTHS = [8192, 32768, 131072, 262144]
PROBE_SEED = 20261007
REPEAT_VARIANTS = 200
