import argparse
import csv
import logging
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display on the server
import matplotlib.pyplot as plt
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import PROJ_ROOT, TARGET_SUBJECTS, BASELINE_FUZZERS
from src.utils.configs import EXPERIMENT_BUCKET

COVERAGE_BASE = PROJ_ROOT / "data" / "coverage"

# We plot branch coverage (absolute covered count). For bbcov, the CSV's
# "branch_covered" column holds the basic-block count.
SOURCE_YLABEL = {
    "gcov": "branches covered",
    "bbcov": "basic blocks covered",
}

# Stable fuzzer order + color, keyed by EXPERIMENT_BUCKET key (the label we plot).
FUZZER_ORDER = list(EXPERIMENT_BUCKET.keys())
FUZZER_COLOR = {key: f"C{i}" for i, key in enumerate(FUZZER_ORDER)}

# A trial is a list of (frame_index, end_time_hours, branch_covered) tuples.
Trial = list[tuple[int, float, float]]


class ParsedArgv:
    def __init__(self, outputs_dir: Path, experiment_name: str):
        self.outputs_dir = outputs_dir
        # `experiment_name` (the parser label) keys the destination dirs; it is
        # distinct from each fuzzer's source run name in EXPERIMENT_BUCKET.
        self.experiment_name = experiment_name
        # All fuzzers are overlaid in one graph, under this experiment label.
        self.dest_png_dir = COVERAGE_BASE / "png" / experiment_name
        self.dest_png_dir.mkdir(parents=True, exist_ok=True)

    def csv_dir_for(self, fuzzer_key: str) -> Path:
        """data/coverage/csv/<fuzzer>/<experiment_name>/ for one fuzzer."""
        return COVERAGE_BASE / "csv" / fuzzer_key / self.experiment_name


def parse_argv() -> ParsedArgv | None:
    parser = argparse.ArgumentParser(
        description="Collect per-trial coverage CSVs for every fuzzer and plot "
        "mean+range branch coverage over time per subject, one line per fuzzer."
    )
    parser.add_argument(
        "-o",
        "--outputs-dir",
        help="Outputs dir containing "
        "<target>/baseline_fuzzing/<fuzzer>/<experiment>/coverage/*.csv",
        required=True,
        metavar="OUTPUTS_DIR",
    )
    parser.add_argument(
        "-e",
        "--experiment-name",
        help="Experiment label for the destination csv/png dirs under data/coverage/.",
        required=True,
        metavar="EXPERIMENT_NAME",
    )
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir).resolve().absolute()
    if not outputs_dir.exists() or not outputs_dir.is_dir():
        logging.error(f"{outputs_dir} does not exist or is not a directory.")
        return None

    return ParsedArgv(outputs_dir, args.experiment_name)


def collect_csvs(parsed_argv: ParsedArgv) -> dict[str, int]:
    """Copy each fuzzer's per-trial coverage CSVs into its central csv dir.

    For every fuzzer in EXPERIMENT_BUCKET, looks at
    <outputs>/<target>/baseline_fuzzing/<FuzzerClass>/<experiment>/coverage/*.{gcov,bbcov}.csv
    and copies them into data/coverage/csv/<fuzzer>/<experiment_name>/.
    Filenames already encode <target>.<fuzz_id>, so the flat dir stays
    collision-free across subjects and trials. A fuzzer that produced no results
    for a subject (e.g. some subjects don't build under Angora) is simply skipped.
    """
    copied_per_fuzzer: dict[str, int] = {}

    for fuzzer_key, experiment_name in EXPERIMENT_BUCKET.items():
        class_dir = BASELINE_FUZZERS.get(fuzzer_key)
        if class_dir is None:
            logging.warning(f"Skipping '{fuzzer_key}': no BASELINE_FUZZERS entry.")
            continue

        dest_csv_dir = parsed_argv.csv_dir_for(fuzzer_key)
        dest_csv_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        for target_dir in sorted(parsed_argv.outputs_dir.iterdir()):
            if not target_dir.is_dir() or target_dir.name not in TARGET_SUBJECTS:
                continue

            coverage_dir = (
                target_dir / "baseline_fuzzing" / class_dir / experiment_name / "coverage"
            )
            if not coverage_dir.is_dir():
                # This fuzzer didn't run (or produced no coverage) for this subject.
                logging.debug(f"[{fuzzer_key}] no coverage dir for {target_dir.name}.")
                continue

            for extension in (".gcov.csv", ".bbcov.csv"):
                for csv_path in sorted(coverage_dir.glob(f"*{extension}")):
                    dest = dest_csv_dir / csv_path.name
                    shutil.copy2(str(csv_path), str(dest))
                    copied += 1
                    logging.info(f"[{fuzzer_key}] Copied {csv_path.name} -> {dest}")

        copied_per_fuzzer[fuzzer_key] = copied
        if copied == 0:
            logging.warning(f"[{fuzzer_key}] No coverage CSVs found for {experiment_name}.")

    return copied_per_fuzzer


def read_trial(csv_path: Path) -> Trial:
    """Read one trial CSV into (frame, end_time_hours, branch_covered) rows.

    The `range` column is "<start>-<end>" minutes; we use the end as the frame's
    elapsed time. A branch_covered of -1 (extraction failure) becomes NaN so it
    doesn't drag the curve down.
    """
    trial: Trial = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                frame = int(row["frame"])
                end_min = int(row["range"].split("-")[1])
                covered = int(row["branch_covered"])
            except (KeyError, ValueError, IndexError):
                continue
            value = float(covered) if covered >= 0 else float("nan")
            trial.append((frame, end_min / 60.0, value))
    trial.sort()
    return trial


def load_grouped(parsed_argv: ParsedArgv) -> dict[tuple[str, str], dict[str, list[Trial]]]:
    """Group every fuzzer's copied CSVs by (subject, source) -> {fuzzer: [trials]}."""
    groups: dict[tuple[str, str], dict[str, list[Trial]]] = defaultdict(lambda: defaultdict(list))

    for fuzzer_key in FUZZER_ORDER:
        csv_dir = parsed_argv.csv_dir_for(fuzzer_key)
        if not csv_dir.is_dir():
            continue

        for csv_path in sorted(csv_dir.glob("*.csv")):
            name = csv_path.name
            if name.endswith(".gcov.csv"):
                source, stem = "gcov", name[: -len(".gcov.csv")]
            elif name.endswith(".bbcov.csv"):
                source, stem = "bbcov", name[: -len(".bbcov.csv")]
            else:
                continue
            # filename is <target>.<fuzz_id>.<source>.csv; target names contain no dot.
            subject = stem.split(".", 1)[0]
            if subject not in TARGET_SUBJECTS:
                logging.warning(f"Skipping {name}: unknown subject '{subject}'.")
                continue
            trial = read_trial(csv_path)
            if trial:
                groups[(subject, source)][fuzzer_key].append(trial)

    return groups


def aggregate(trials: list[Trial]):
    """Align trials by frame and compute per-frame x, mean, min, max.

    Trials are aligned on frame index (same frame == same time window, since the
    frame size is fixed). Coverage is cumulative/monotonic, so a shorter trial is
    forward-filled with its last value across later frames.
    """
    num_frames = max(t[-1][0] for t in trials) + 1
    longest = max(trials, key=len)
    frame_to_hours = {frame: hours for frame, hours, _ in longest}
    xs = np.array([frame_to_hours.get(frame, np.nan) for frame in range(num_frames)])

    mat = np.full((len(trials), num_frames), np.nan)
    for ti, trial in enumerate(trials):
        by_frame = {frame: value for frame, _, value in trial}
        last = np.nan
        for frame in range(num_frames):
            value = by_frame.get(frame, np.nan)
            if not np.isnan(value):
                last = value
            mat[ti, frame] = last  # forward-fill

    with np.errstate(all="ignore"):
        mean = np.nanmean(mat, axis=0)
        lower = np.nanmin(mat, axis=0)
        upper = np.nanmax(mat, axis=0)
    return xs, mean, lower, upper


def plot_subject(
    subject: str,
    source: str,
    per_fuzzer_trials: dict[str, list[Trial]],
    dest_png_dir: Path,
) -> Path:
    """Plot mean branch coverage with a min-max band, one line per fuzzer."""
    fig, ax = plt.subplots(figsize=(8, 5))

    for fuzzer_key in FUZZER_ORDER:
        trials = per_fuzzer_trials.get(fuzzer_key)
        if not trials:
            continue
        xs, mean, lower, upper = aggregate(trials)
        color = FUZZER_COLOR[fuzzer_key]
        ax.plot(xs, mean, color=color, label=f"{fuzzer_key} ({len(trials)} trial(s))")
        ax.fill_between(xs, lower, upper, color=color, alpha=0.2)

    ax.set_xlabel("fuzzing time (hours)")
    ax.set_ylabel(SOURCE_YLABEL[source])
    ax.set_title(f"{subject} - {source} coverage")
    ax.grid(True, alpha=0.3)
    ax.legend()

    dest_png_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_png_dir / f"{subject}_{source}_branch.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parsed_argv = parse_argv()
    if parsed_argv is None:
        return

    # 1-2. Collect coverage CSVs from each fuzzer/subject and copy them centrally.
    collect_csvs(parsed_argv)

    # 3. Group by (subject, source) and draw one mean+range graph per subject,
    #    overlaying every fuzzer that has data for it.
    groups = load_grouped(parsed_argv)
    if not groups:
        logging.info(f"No coverage CSVs found under {COVERAGE_BASE}.")
        return

    for (subject, source) in sorted(groups):
        per_fuzzer = groups[(subject, source)]
        out_path = plot_subject(subject, source, per_fuzzer, parsed_argv.dest_png_dir)
        present = ", ".join(f"{k}:{len(per_fuzzer[k])}" for k in FUZZER_ORDER if per_fuzzer.get(k))
        logging.info(f"Plotted {subject} {source} [{present}] -> {out_path}")

    logging.info("Coverage plotting complete.")


if __name__ == "__main__":
    main()
