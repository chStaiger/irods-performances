import argparse
from .orchestrator import run_all_tests


def main():
    parser = argparse.ArgumentParser(description="iRODS performance benchmarking tool")

    parser.add_argument("--clients", nargs="+", default=["python", "icommands", "cadaver"])
    parser.add_argument("--sizes", nargs="+", type=int, default=[2, 3, 5])
    parser.add_argument("--small-files", type=int, default=4000)
    parser.add_argument("--small-size", type=int, default=500)
    parser.add_argument("--output", default="irodsPerformances.out.pickle")

    args = parser.parse_args()

    run_all_tests(
        clients=args.clients,
        large_sizes=args.sizes,
        num_small=args.small_files,
        small_size=args.small_size,
        output_file=args.output,
    )

