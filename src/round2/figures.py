"""
Data Vortex -- Round 2: all matplotlib figures.

Every figure is drawn from computed metrics (never hand-typed numbers) and
saved at print resolution for embedding in the two PDF reports. The module
has no state and no randomness -- re-running yields pixel-identical output
for identical inputs.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from round2 import text_clean as tc

plt.rcParams.update({"figure.dpi": 150, "savefig.dpi": 150,
                     "font.size": 9, "axes.titlesize": 10,
                     "axes.titleweight": "bold"})
PALETTE = plt.get_cmap("tab10").colors
SENT_COLORS = {"Negative": "#d95f5f", "Neutral": "#9a9a9a", "Positive": "#4ca64c"}


def _save(fig: plt.Figure, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def fig_label_distributions(profile: dict, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), constrained_layout=True)
    sents = list(profile["sentiment_counts"].items())
    axes[0].bar([k for k, _ in sents], [v for _, v in sents],
                color=[SENT_COLORS.get(k, "#555555") for k, _ in sents])
    axes[0].set_title("Sentiment labels (modeled rows)")
    axes[0].set_ylabel("posts")
    for x, (_, v) in enumerate(sents):
        axes[0].text(x, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
    tops = sorted(profile["topic_counts"].items(), key=lambda kv: -kv[1])
    axes[1].barh([k for k, _ in tops][::-1], [v for _, v in tops][::-1],
                 color=PALETTE[0])
    axes[1].set_title("Topic labels (modeled rows)")
    axes[1].set_xlabel("posts")
    for i, (_, v) in enumerate(tops[::-1]):
        axes[1].text(v, i, f" {v:,}", va="center", fontsize=8)
    _save(fig, path)


def fig_text_lengths(train_df: pd.DataFrame, test_df: pd.DataFrame, path: Path) -> None:
    ltr = train_df["post_text"].map(lambda s: len(tc.base_clean(s)))
    lte = test_df["post_text"].map(lambda s: len(tc.base_clean(s)))
    bins = np.linspace(0, max(ltr.max(), lte.max()), 40)
    fig, ax = plt.subplots(figsize=(7, 3.4), constrained_layout=True)
    ax.hist(ltr, bins=bins, histtype="step", linewidth=1.5, label=f"train (n={len(ltr):,})")
    ax.hist(lte, bins=bins, histtype="step", linewidth=1.5, label=f"test (n={len(lte):,})")
    ax.axvline(ltr.median(), ls="--", lw=1, color="gray")
    ax.text(ltr.median(), ax.get_ylim()[1] * 0.92, f" median {ltr.median():.0f} chars",
            fontsize=8, color="gray")
    ax.set_title("Post length distribution (cleaned chars)")
    ax.set_xlabel("characters")
    ax.set_ylabel("posts")
    ax.legend()
    _save(fig, path)


def fig_confusion(cm: list[list[int]], labels: list[str], title: str,
                  path: Path, normalize: bool) -> None:
    arr = np.array(cm, dtype=float)
    if normalize:
        arr = arr / arr.sum(axis=1, keepdims=True).clip(min=1)
    fig, ax = plt.subplots(figsize=(5.2, 4.6), constrained_layout=True)
    im = ax.imshow(arr, cmap="Blues", vmin=0, vmax=1 if normalize else None)
    ax.set_title(title)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            txt = f"{arr[i, j]:.2f}" if normalize else f"{int(arr[i, j]):,}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9,
                    color="white" if arr[i, j] > (0.5 if normalize else arr.max() / 2)
                    else "black")
    fig.colorbar(im, ax=ax, shrink=0.8)
    _save(fig, path)


def fig_cv_compare(specs: dict, title: str, path: Path) -> None:
    names = sorted(specs, key=lambda n: -specs[n]["cv_mean"])
    means = [specs[n]["cv_mean"] for n in names]
    stds = [specs[n]["cv_std"] for n in names]
    colors = [PALETTE[2] if i == 0 else PALETTE[0] for i in range(len(names))]
    fig, ax = plt.subplots(figsize=(7, 3.6), constrained_layout=True)
    ax.bar(names, means, yerr=stds, capsize=4, color=colors)
    ax.set_title(title + "  (best in green)")
    ax.set_ylabel("macro-F1")
    ax.set_xticklabels(names, rotation=20, ha="right")
    ax.set_ylim(min(means) - 3 * max(stds + [0.01]), max(means) + 3 * max(stds + [0.01]))
    for x, (m, s) in enumerate(zip(means, stds)):
        ax.text(x, m + s + 0.002, f"{m:.3f}", ha="center", fontsize=8)
    _save(fig, path)


def fig_roc(rocs: dict, auc_overall: float | None, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 4.6), constrained_layout=True)
    for i, (lab, curve) in enumerate(rocs.items()):
        ax.plot(curve["fpr"], curve["tpr"], lw=1.8, color=PALETTE[i % len(PALETTE)],
                label=f"{lab} (AUC {curve['auc']:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color="gray", label="chance")
    ax.set_title(title if auc_overall is None else f"{title}  [OvR AUC {auc_overall:.3f}]")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    _save(fig, path)


def fig_reliability(calib: dict, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 4.6), constrained_layout=True)
    ax.plot([0, 1], [0, 1], ls="--", color="gray", label="perfectly calibrated")
    for i, (lab, curve) in enumerate(calib.items()):
        ax.plot(curve["prob_pred"], curve["prob_true"], marker="o", ms=3,
                color=PALETTE[i % len(PALETTE)], label=lab)
    ax.set_title(title)
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("empirical positive rate")
    ax.legend(fontsize=8)
    _save(fig, path)


def fig_learning_curve(lcurve: dict, title: str, path: Path) -> None:
    x = np.array(lcurve["train_sizes"])
    fig, ax = plt.subplots(figsize=(6.4, 3.8), constrained_layout=True)
    ax.errorbar(x, lcurve["train_mean"], yerr=lcurve["train_std"], marker="o",
                ms=3, capsize=3, label="train (3-fold)")
    ax.errorbar(x, lcurve["valid_mean"], yerr=lcurve["valid_std"], marker="s",
                ms=3, capsize=3, label="validation (3-fold)")
    ax.set_title(title)
    ax.set_xlabel("train rows")
    ax.set_ylabel("macro-F1")
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, path)


def fig_slices(slices: dict, title: str, path: Path) -> None:
    order = ["overall"] + [k for k in slices if k.startswith("len_")] + \
            [k for k in slices if k not in ("overall",) and not k.startswith("len_")]
    names = [k for k in order if slices[k]["n"]]
    accs = [slices[k]["accuracy"] for k in names]
    colors = [PALETTE[2] if k == "overall" else PALETTE[0] for k in names]
    fig, ax = plt.subplots(figsize=(8.2, 3.8), constrained_layout=True)
    ax.bar(names, accs, color=colors)
    ax.set_title(title)
    ax.set_ylabel("accuracy")
    ax.set_xticks(range(len(names)),
                  [f"{k}\n(n={slices[k]['n']:,})" for k in names],
                  rotation=25, ha="right", fontsize=8)
    for x, a in enumerate(accs):
        ax.text(x, a, f"{a:.3f} ", ha="center", va="bottom", fontsize=8, rotation=90)
    _save(fig, path)


def fig_lda_top_words(unsupervised: dict, path: Path) -> None:
    """Ranked word lists per discovered topic (rank = component weight order).

    WHY text panels, not bars: only the word ranking is persisted (weights
    live in the model file); a bar chart would need numbers we chose not to
    duplicate, while the ranking is exactly what a reader needs to judge
    topic coherence.
    """
    for algo in ("lda", "nmf"):
        block = unsupervised[algo]
        topics = sorted(block["top_words"])
        ncols = 2
        nrows = (len(topics) + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=(9, 1.6 * nrows + 0.8),
                                 constrained_layout=True)
        axes = np.atleast_1d(axes).ravel()
        for ax, t in zip(axes, topics):
            words = block["top_words"][t]
            ax.axis("off")
            ax.set_title(f"{algo.upper()} {t}", fontsize=10, loc="left")
            ax.text(0.02, 0.92, "\n".join(f"{i + 1:2d}. {w}" for i, w in enumerate(words)),
                    transform=ax.transAxes, va="top", fontsize=9, family="monospace",
                    bbox=dict(boxstyle="round,pad=0.4", fc="#f4f6fb", ec="#c9d4e8"))
        for ax in axes[len(topics):]:
            ax.axis("off")
        fig.suptitle(f"Discovered topics -- {algo.upper()} top-10 words (ranked)",
                     fontweight="bold")
        _save(fig, Path(str(path)).with_name(f"r2_10_{algo}_words.png"))


def fig_agreement_heatmap(unsupervised: dict, path: Path) -> None:
    topics = unsupervised["topics"]
    discovered = [f"T{i}" for i in range(unsupervised["K"])]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
    for ax, algo in zip(axes, ("lda", "nmf")):
        block = unsupervised[algo]
        arr = np.array(block["contingency"], dtype=float)
        norm = arr / arr.sum(axis=1, keepdims=True).clip(min=1)
        im = ax.imshow(norm, cmap="Greens", vmin=0, vmax=1)
        agree = block["agreement"]
        ax.set_title(f"{algo.upper()}  NMI {agree['nmi']:.3f} · ARI {agree['ari']:.3f}")
        ax.set_xlabel("discovered topic (argmax)")
        ax.set_ylabel("human topic label")
        ax.set_xticks(range(len(discovered)), discovered, rotation=0)
        ax.set_yticks(range(len(topics)), topics, fontsize=8)
        for i in range(len(topics)):
            for j in range(len(discovered)):
                ax.text(j, i, f"{norm[i, j]:.2f}\n({int(arr[i, j])})",
                        ha="center", va="center", fontsize=7,
                        color="white" if norm[i, j] > 0.5 else "black")
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.suptitle("Unsupervised-vs-human agreement (row-normalised, counts in brackets)",
                 fontweight="bold")
    _save(fig, path)
