import argparse
import pickle
from .orchestrator import run_all_tests
from .plot import plot_results


def main():
    """Main CLI."""
    parser = argparse.ArgumentParser(
        prog="irodsperf",
        description="iRODS performance benchmarking tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--all", action="store_true",
                        help="Run all benchmarks using default parameters")

    parser.add_argument("--plot", metavar="PICKLE",
                        help="Plot results from a pickle file")

    parser.add_argument("--plot-out", default="plot.png",
                        help="Filename for saving the plot")

    parser.add_argument("--clients", nargs="+", default=None,
                        help="Clients to benchmark")
    parser.add_argument("--sizes", nargs="+", type=int, default=None,
                        help="Large file sizes in GB")
    parser.add_argument("--small-files", type=int, default=None,
                        help="Number of small files to generate")
    parser.add_argument("--small-size", type=int, default=None,
                        help="Size of each small file in KB")
    parser.add_argument("--output", default=None,
                        help="Output pickle file")

    args = parser.parse_args()

    # --- CASE 1: Plotting mode ---
    if args.plot:
        with open(args.plot, "rb") as f:
            results = pickle.load(f)
        plot_results(results, outfile=args.plot_out)
        return

    # --- CASE 2: No arguments at all → show help ---
    import sys
    if len(sys.argv) == 1:
        parser.print_help()
        return

    # --- CASE 3: Determine run parameters ---
    # Defaults (used when --all is given OR user doesn't override)
    defaults = {
        "clients": ["python", "icommands", "cadaver"],
        "sizes": [2, 3, 5],
        "small_files": 4000,
        "small_size": 500,
        "output_file": "irodsPerformances.out.pickle",
    }

    # If user passed --all, start with defaults
    if args.all:
        run_params = defaults.copy()
    else:
        # User wants a custom run
        run_params = defaults.copy()

    # Override defaults with user-specified values
    if args.clients is not None:
        run_params["clients"] = args.clients
    if args.sizes is not None:
        run_params["sizes"] = args.sizes
    if args.small_files is not None:
        run_params["small_files"] = args.small_files
    if args.small_size is not None:
        run_params["small_size"] = args.small_size
    if args.output is not None:
        run_params["output_file"] = args.output

    print("\n=== Running benchmark with parameters ===")
    for key, value in run_params.items():
        print(f"{key:15}: {value}")
    print("========================================\n")

    # --- CASE 4: Run benchmark ---
    run_all_tests(
        clients=run_params["clients"],
        large_sizes=run_params["sizes"],
        num_small=run_params["small_files"],
        small_size=run_params["small_size"],
        output_file=run_params["output_file"],
    )

