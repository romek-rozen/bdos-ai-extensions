"""Optional 2D UMAP scatter of clustered embeddings.

Readable render: noise drawn faint underneath, smaller clusters in a light tint,
and the top-N largest clusters colored + numbered with a side legend that maps
each number to a representative phrase (the member nearest its centroid) and the
cluster size. Avoids the unreadable default of N recycled colors + noise on top.
"""
import pathlib

TOP_N = 15


def scatter(vectors, labels, texts, out_dir="keyword_cluster/outputs", top_n=TOP_N):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from collections import Counter

    arr = np.asarray(vectors, dtype=float)
    labs = np.asarray(labels)
    texts = list(texts)

    if len(arr) < 3:
        # UMAP cannot produce a meaningful 2D embedding for <3 points; trivial layout.
        coords = np.zeros((len(arr), 2), dtype=float)
        for i in range(len(arr)):
            coords[i, 0] = float(i)
    else:
        import umap
        n_neighbors = max(2, min(15, len(arr) - 1))
        # cosine matches the whitened-cosine space the labels were clustered in.
        coords = umap.UMAP(n_neighbors=n_neighbors, min_dist=0.2,
                           metric="cosine", random_state=42).fit_transform(arr)

    sizes = Counter(int(l) for l in labs if l >= 0)
    top = [lab for lab, _ in sizes.most_common(top_n)]
    small = [l for l in sizes if l not in top]

    def representative(lab):
        idx = np.where(labs == lab)[0]
        c = coords[idx].mean(axis=0)
        best = idx[np.argmin(((coords[idx] - c) ** 2).sum(axis=1))]
        return texts[best]

    fig, ax = plt.subplots(figsize=(16, 11))
    # noise faint, underneath
    m = labs < 0
    if m.any():
        ax.scatter(coords[m, 0], coords[m, 1], s=7, c="#e0e0e0",
                   alpha=0.45, linewidths=0, zorder=1)
    # smaller clusters as a light tint
    for lab in small:
        mk = labs == lab
        ax.scatter(coords[mk, 0], coords[mk, 1], s=22, c="#c6dbef",
                   alpha=0.55, linewidths=0, zorder=2)
    # top clusters colored + numbered
    cmap = plt.cm.tab20(np.linspace(0, 1, 20))
    legend = []
    for n, lab in enumerate(top, 1):
        mk = labs == lab
        color = cmap[(n - 1) % 20]
        ax.scatter(coords[mk, 0], coords[mk, 1], s=55, color=color,
                   alpha=0.9, edgecolors="white", linewidths=0.4, zorder=3)
        cx, cy = coords[mk, 0].mean(), coords[mk, 1].mean()
        ax.annotate(str(n), (cx, cy), fontsize=15, fontweight="bold",
                    ha="center", va="center", zorder=6, color="black",
                    bbox=dict(boxstyle="circle,pad=0.28", fc="white", ec=color, lw=2))
        legend.append(f"{n:>2}.  {representative(lab)[:34]:34}  ·  {sizes[lab]:>3} kw")

    if legend:
        noise_n = int(m.sum())
        txt = ("CLUSTERS (top %d by size):\n\n" % len(top) + "\n".join(legend) +
               "\n\n     · grey = noise (%d) · light blue = smaller clusters (%d)"
               % (noise_n, len(small)))
        ax.text(1.02, 0.98, txt, transform=ax.transAxes, fontsize=10.5, va="top",
                family="monospace",
                bbox=dict(boxstyle="round,pad=0.6", fc="#fafafa", ec="#bbbbbb"))

    ax.set_title("Keyword clusters — whitened-cosine → UMAP projection",
                 fontsize=13, fontweight="bold")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor("#dddddd")

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = str(out / "keyword_clusters.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path
