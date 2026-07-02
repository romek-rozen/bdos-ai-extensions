"""Optional 2D UMAP scatter of clustered embeddings."""
import pathlib


def scatter(vectors, labels, texts, out_dir="keyword_cluster/outputs"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    arr = np.asarray(vectors, dtype=float)
    if len(arr) < 3:
        # UMAP cannot produce a meaningful 2D embedding for <3 points; use a trivial layout.
        coords = np.zeros((len(arr), 2), dtype=float)
        for i in range(len(arr)):
            coords[i, 0] = float(i)
    else:
        import umap
        n_neighbors = max(2, min(15, len(arr) - 1))
        coords = umap.UMAP(n_neighbors=n_neighbors, min_dist=0.1,
                           metric="euclidean", random_state=42).fit_transform(arr)
    fig, ax = plt.subplots(figsize=(12, 9))
    labs = np.asarray(labels)
    for lab in sorted(set(labs)):
        m = labs == lab
        name = "noise" if lab < 0 else f"cluster {lab}"
        ax.scatter(coords[m, 0], coords[m, 1], s=30, alpha=0.7, label=name)
    ax.legend(fontsize=8, loc="best")
    ax.set_title("Keyword clusters (UMAP projection)")
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = str(out / "keyword_clusters.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path
