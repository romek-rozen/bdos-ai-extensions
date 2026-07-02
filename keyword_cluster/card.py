"""Terminal-style PNG "card" of clusters — a shareable summary image.

Renders the top-N clusters as a dark, monospace terminal card (box header +
colored cluster rows + first-K keywords each, with optional per-keyword search
volume). Meant for a quick, presentable screenshot; the analytical view is
``viz.scatter`` (the UMAP projection).

    from my.extensions.keyword_cluster import cluster, card
    res = cluster(keywords, method="semantic")
    card(res["clusters"], title="Sklep X", subtitle="60 fraz → grupy",
         kw_volume={"biala koszulka": 4400, ...})
"""
import pathlib

BG = "#0d1117"
FG = "#c9d1d9"
DIM = "#6e7681"
CY = "#39c5cf"
ACCENTS = ["#e3b341", "#39c5cf", "#f778ba", "#58a6ff", "#bc8cff", "#3fb950",
           "#e3b341", "#ff7b72"]
MONO = {"family": "monospace"}


def card(clusters, out_dir="keyword_cluster/outputs", *, top_n=12, keys_per=5,
         title="KLASTROWANIE SEMANTYCZNE FRAZ", subtitle=None, kw_volume=None,
         filename="keyword_clusters_card.png"):
    """Render a terminal-style cluster card to a PNG. Returns the path.

    clusters : list of cluster dicts from ``cluster()`` (needs ``label``,
               ``members``, ``size``; ``total_volume`` used if present).
    kw_volume: optional ``{keyword: monthly_volume}`` for a per-line volume column
               and volume-based cluster sorting.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    kw_volume = kw_volume or {}

    def cvol(c):
        if kw_volume:
            return sum(kw_volume.get(m, 0) for m in c["members"])
        return c.get("total_volume") or 0

    rows = sorted(clusters, key=cvol, reverse=True)[:top_n]

    fig = plt.figure(figsize=(13, 13), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 100)

    def T(x, y, s, c=FG, size=13, w="normal"):
        ax.text(x, y, s, color=c, fontsize=size, fontweight=w, va="top", **MONO)

    y = 97
    T(4, y, "╭" + "─" * 72 + "╮", CY); y -= 2.0
    T(4, y, "│", CY); T(7, y, ">_ " + title[:60], FG, 15, "bold"); T(75.5, y, "│", CY); y -= 1.9
    if subtitle:
        T(4, y, "│", CY); T(7, y, subtitle[:70], DIM, 11.5); T(75.5, y, "│", CY); y -= 1.9
    T(4, y, "│", CY); T(7, y, "qwen3-8b embeddings → whitened-cosine → auto-grupy pod Google Ads", DIM, 11.5); T(75.5, y, "│", CY); y -= 2.0
    T(4, y, "╰" + "─" * 72 + "╯", CY); y -= 3.4

    for i, c in enumerate(rows, 1):
        col = ACCENTS[(i - 1) % len(ACCENTS)]
        v = cvol(c)
        T(5, y, f"◆ {i:>2}.", col, 14, "bold")
        T(14, y, str(c["label"])[:34], col, 14, "bold")
        vtxt = f"{c['size']} fraz · {v:>5} vol/mc" if kw_volume else f"{c['size']} fraz"
        T(66, y, vtxt, DIM, 11); y -= 1.9
        for m in c["members"][:keys_per]:
            T(15, y, "•", col, 12)
            T(17, y, str(m)[:44], FG, 12)
            if kw_volume:
                T(64, y, f"{kw_volume.get(m, 0):>5}", DIM, 10.5)
            y -= 1.5
        y -= 1.2

    T(5, y, "♥", "#f778ba", 13)
    T(8, y, "BDOS-AI · keyword_cluster · semantic auto-grouping · <3", DIM, 11)
    y -= 1.5

    ax.set_ylim(y, 98)
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = str(out / filename)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG, pad_inches=0.35)
    plt.close(fig)
    return path
