import matplotlib.pyplot as plt
import pandas as pd


def plot_results(results, outfile="plot.png"):
    """Plot results from run stored in pkl file."""
    # Convert UploadResult objects into a DataFrame
    df = pd.DataFrame([{
        "data": r.data,
        "duration": r.duration,
        "checksum": r.checksum,
        "client": r.client
    } for r in results])

    # Extract size label (1GB, 64KB, etc.)
    df["size"] = (
        df["data"]
        .str.extract(r"(\d+GB|\d+MB|\d+KB)", expand=False)
    )

    # Identify small files (no size match → small batch)
    df["size"] = df["size"].fillna("Folder")

    # Normalize checksum labels
    df["checksum"] = df["checksum"].map({True: "-K", False: ""})

    # Combine client + checksum into a single method label
    df["method"] = df["client"] + df["checksum"]

    # --- NEW PART: sum small-file durations ---
    summary = (
        df.groupby(["method", "size"])["duration"]
        .mean()
        .reset_index()
    )

    # Pivot for plotting
    pivot = summary.pivot(index="size", columns="method", values="duration")

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    pivot.plot(kind="bar", ax=ax)

    ax.set_ylabel("Time (s)")
    ax.set_title("Data Transfer Performance")
    ax.legend(title="Client")
    plt.xticks(rotation=0)
    plt.tight_layout()

    fig.savefig(outfile)
    print(f"Plot saved to {outfile}")
