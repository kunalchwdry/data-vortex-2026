# Dataset 2 -- cleaning + split report

Source: `data/round2/raw/Dataset2.csv` (never modified)

## Row reconciliation

`9000 raw - 0 empty - 1100 exact-duplicate = 7900 modeled`

Same-text conflicting labels kept as label noise: **0** distinct texts

## Label distribution (modeled rows)

| sentiment | n |
|---|---|
| Negative | 2430 |
| Neutral | 2748 |
| Positive | 2722 |

| topic | n |
|---|---|
| Account_Security | 129 |
| Community_Discussion | 6803 |
| Feature_Feedback | 250 |
| Technical_Issues | 718 |

## Text length (chars, cleaned)

min 24 · median 112 · mean 106.5 · max 158

## Split

seed 42 · test 0.2 · stratify `sentiment_x_topic` · train 6320 / test 1580 · id overlap 0
