import argparse
import pickle
from .orchestrator import run_all_tests
from .plot import plot_results

def main():
    parser = argparse.ArgumentParser(
        prog="irodsperf",
        description="iRODS performance benchmarking tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the full benchmark with the selected parameters",
    )

    parser.add_argument("--clients", nargs="+", default=["python", "icommands", "cadaver"],
                        help="Clients to benchmark")
    parser.add_argument("--sizes", nargs="+", type=int, default=[2, 3, 5],
                        help="Large file sizes in GB")
    parser.add_argument("--small-files", type=int, default=4000,
                        help="Number of small files to generate")
    parser.add_argument("--small-size", type=int, default=500,
                        help="Size of each small file in KB")
    parser.add_argument("--output", default="irodsPerformances.out.pickle",
                        help="Output pickle file")
    parser.add_argument(
        "--plot",
        metavar="PICKLE",
        help="Plot results from a pickle file instead of running benchmarks",
    )
    parser.add_argument(
        "--plot-out",
        default="plot.png",
        help="Filename for saving the plot"
    )

    args = parser.parse_args()

    # --- CASE 1: Plotting mode ---
    if args.plot:
        with open(args.plot, "rb") as f:
            results = pickle.load(f)
        plot_results(results, outfile=args.plot_out)
        return

    # --- CASE 2: Benchmark mode ---
    if args.all:
        run_all_tests(
            clients=args.clients,
            large_sizes=args.sizes,
            num_small=args.small_files,
            small_size=args.small_size,
            output_file=args.output,
        )
        return

    # --- CASE 3: No arguments → show help ---
    parser.print_help()
