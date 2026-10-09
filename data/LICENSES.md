# Data and model licences

The licence fields in `data/manifest.json` are kept as recorded for the run (the manifest is a
scientific input and is hashed). This file corrects and extends them.

| Input | Licence or terms | Source |
|---|---|---|
| Findlay et al. 2018 BRCA1 table (`41586_2018_461_MOESM3_ESM.xlsx`) | Function scores are "freely available for all nonprofit uses"; commercial entities need a licence. Copying it into Arc's Apache-2.0 repository does not relicense it. This study is a nonprofit use (confirmed by the study owner, 9 October 2026) and does not redistribute the table. | Findlay et al. 2018, Data Availability, https://pmc.ncbi.nlm.nih.gov/articles/PMC6181777 |
| GRCh37.p13 chromosome 17 | NCBI reference assembly, public domain | NCBI |
| `samplePositions.tsv`, `prompts.csv` | Apache-2.0 (ArcInstitute/evo2) | https://github.com/ArcInstitute/evo2 |
| Evo 2 weights (`arcinstitute/evo2_7b`, `evo2_7b_base`) | Apache-2.0 | Hugging Face model cards |
| Exon classifier (`schmojo/evo2-exon-classifier`) | Apache-2.0 | Hugging Face model card, revision 3ce7ccd |
| CADD v1.3 and phyloP values | Used as supplied in the Findlay et al. table | Findlay et al. 2018 Methods |
