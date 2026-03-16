import argparse
import csv
import os
import sys

from typing import Any, Callable, Iterable, TypeAlias

import torch

from model import discover_extensions, load_extension

Metric: TypeAlias = Callable[[str, float, float, float, float, float], float | None]
Filter: TypeAlias = Callable[[str, float, float, float, float, float, float], bool]

def custom_metric(
    tag: str, threshold: float,
    tp: float, fp: float, tn: float, fn: float
) -> float | None:
    raise NotImplementedError("Edit this function to define a custom metric.")

def cti_metric(
    _tag: str, _threshold: float,
    tp: float, fp: float, _tn: float, fn: float
) -> float:
    return tp / (tp + fp + fn) if tp else 0.0

def j_metric(
    _tag: str, _threshold: float,
    tp: float, fp: float, tn: float, fn: float
) -> float:
    return (
        (tp / (tp + fn) if tp else 0.0) +
        (tn / (tn + fp) if tn else 0.0) -
        1.0
    )

def p4_metric(
    _tag: str, _threshold: float,
    tp: float, fp: float, tn: float, fn: float
) -> float:
    n = 4.0 * tp * tn
    return n / (n + (tp + tn) * (fp + fn)) if n else 0.0

def f_score(beta: float = 1.0) -> Metric:
    if beta <= 0.0:
        raise ValueError("beta must be positive")

    w_fn = beta * beta
    w_tp = 1.0 + w_fn

    def _f_beta_metric(
        tag: str, threshold: float,
        tp: float, fp: float, tn: float, fn: float
    ) -> float:
        return cti_metric(tag, threshold, tp * w_tp, fp, tn, fn * w_fn)

    return _f_beta_metric

def score_filter(min_score: float) -> Filter:
    def _score_filter(
        _tag: str, _threshold: float, score: float,
        _tp: float, _fp: float, _tn: float, _fn: float
    ):
        return score >= min_score

    return _score_filter

def pr_filter(min_precision: float, min_recall: float) -> Filter:
    def _pr_filter(
        _tag: str, _threshold: float, _score: float,
        tp: float, fp: float, _tn: float, fn: float
    ):
        if tp == 0.0:
            return min_precision <= 0.0 and min_recall <= 0.0

        return (
            (tp / (tp + fp)) >= min_precision
            and (tp / (tp + fn)) >= min_recall
        )

    return _pr_filter

def threshold_filter(min_threshold: float, max_threshold: float) -> Filter:
    def _threshold_filter(
        _tag: str, threshold: float, _score: float,
        _tp: float, _fp: float, _tn: float, _fn: float
    ):
        return min_threshold <= threshold <= max_threshold

    return _threshold_filter

def tag_filter(blocked_tags: Iterable[str]) -> Filter:
    if not isinstance(blocked_tags, set | frozenset):
        blocked_tags = set(blocked_tags)

    def _tag_filter(
        tag: str, _threshold: float, _score: float,
        _tp: float, _fp: float, _tn: float, _fn: float
    ):
        return tag not in blocked_tags

    return _tag_filter

def apply_filter(metric: Metric, filter_fn: Filter) -> Metric:
    def filtered(
        tag: str, threshold: float,
        tp: float, fp: float, tn: float, fn: float
    ):
        score = metric(tag, threshold, tp, fp, tn, fn)
        if (
            score is None
            or not filter_fn(tag, threshold, score, tp, fp, tn, fn)
        ):
            return None

        return score

    return filtered

class Calibrator:
    def __init__(self, metric: Metric) -> None:
        self.metric = metric
        self.best: dict[str, tuple[float, float]] = {}
        self.ext_labels: dict[str, str] = {}

    def add_csv(self, path: str) -> None:
        with open(path, "r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                self.add(
                    row["tag"], float(row["threshold"]),
                    float(row["tp"]), float(row["fp"]), float(row["tn"]), float(row["fn"]),
                )

    def add_extension(self, path: str) -> bool:
        info, data = load_extension(path)
        tag = info["label"]

        try:
            val_data = data["validation"]
        except KeyError:
            return False

        if (conflict_path := self.ext_labels.get(tag)) is not None:
            raise RuntimeError(f"Extension {repr(path)} conflicts with extension {repr(conflict_path)} over label {repr(tag)}.")

        self.ext_labels[tag] = path
        self.best.pop(tag, None)

        thresholds = (
            torch.linspace(
                0.0, 1.0, val_data.size(0) + 2,
                device="cpu", dtype=torch.float32
            )[1:-1]
                .logit_()
                .to(dtype=torch.bfloat16)
                .to(dtype=torch.float32)
                .sigmoid_()
        )

        for threshold, (tp, fp, tn, fn) in zip(thresholds.tolist(), val_data.tolist()):
            self.add(tag, threshold, tp, fp, tn, fn)

        return True

    def add(self, tag: str, threshold: float, tp: float, fp: float, tn: float, fn: float) -> None:
        score = self.metric(tag, threshold, tp, fp, tn, fn)
        if score is not None:
            tag_best = self.best.get(tag)
            if tag_best is None or (score, -threshold) > (tag_best[1], -tag_best[0]):
                self.best[tag] = (threshold, score)

if __name__ == "__main__":
    def main() -> None:
        parser = argparse.ArgumentParser()

        parser.add_argument(
            "--data", default="data/jtp-3-hydra-val.csv",
            help="Path to .csv validation data file."
        )
        parser.add_argument("-e", "--extension", action="append", default=[],
            metavar="PATH",
            help=(
                "Path to extension. May be specified multiple times. "
                "If a directory is specified, all extensions in the specified directory are calibrated. "
                "(Default: extensions/jtp-3-hydra)"
            ))
        parser.add_argument("-E", "--no-default-extensions", action="store_true",
            help="Do not calibrate extensions by default."
        )

        parser.add_argument(
            "-o", "--output", default="calibration.csv",
            metavar="PATH",
            help="Path to output .csv calibration file, or '-' for standard output. (Default: calibration.csv)"
        )

        parser.add_argument("-m", "--metric", default="cti",
            metavar="METRIC",
            help="Scoring metric. (cti, f<beta>, j, p4, custom; default: cti)"
        )
        parser.add_argument(
            "-s", "--min-score", type=float,
            metavar="SCORE",
            help="Require a minimum value for the metric."
        )
        parser.add_argument(
            "-R", "--range", type=float, nargs=2,
            metavar=("MIN", "MAX"),
            help="Restrict calibration range."
        )
        parser.add_argument(
            "-p", "--min-precision", type=float, default=0.098,
            metavar="PRECISION",
            help="Require a minimum precision. (Default: 0.098)"
        )
        parser.add_argument(
            "-r", "--min-recall", type=float, default=0.198,
            metavar="RECALL",
            help="Require a minimum recall. (Default: 0.198)"
        )
        parser.add_argument(
            "-x", "--exclude-tags", nargs="*",
            help="Exclude the specified tags."
        )
        parser.add_argument(
            "--epsilon", type=float, default=-0.0001,
            metavar="EPS",
            help="Adjust final thresholds after filtering. (Default: -0.0001)"
        )

        args = parser.parse_args()
        args.metric = args.metric.lower()

        metric: Metric
        if args.metric == "custom":
            metric = custom_metric
        elif args.metric in ("ts", "csi", "cti"):
            metric = cti_metric
        elif args.metric in ("j", "bmi"):
            metric = j_metric
        elif args.metric == "p4":
            metric = p4_metric
        elif args.metric.startswith("f"):
            try:
                metric = f_score(float(args.metric[1:]))
            except ValueError:
                parser.error("Beta for F-score metric must be a positive number.")
        else:
            parser.error("Unrecognized metric.")

        if args.min_score is not None:
            metric = apply_filter(metric, score_filter(args.min_score))

        if args.range is not None:
            metric = apply_filter(metric, threshold_filter(*args.range))

        if args.min_precision is not None:
            metric = apply_filter(metric, pr_filter(args.min_precision, 0.0))

        if args.min_recall is not None:
            metric = apply_filter(metric, pr_filter(0.0, args.min_recall))

        if args.exclude_tags:
            metric = apply_filter(metric, tag_filter(args.exclude_tags))

        if (
            not args.extension
            and not args.no_default_extensions
            and os.path.isdir("extensions/jtp-3-hydra")
        ):
            args.extension.append("extensions/jtp-3-hydra")

        calibrator = Calibrator(metric)
        calibrator.add_csv(args.data)

        for ext_path in discover_extensions(args.extension):
            if calibrator.add_extension(ext_path):
                print(f"Calibrated extension {repr(ext_path)}.", file=sys.stderr)
            else:
                print(f"Skipping extension {repr(ext_path)} without calibration data.", file=sys.stderr)

        print(f"Calibrated {len(calibrator.best)} tags.", file=sys.stderr)

        out_file: Any = None
        writer: Any

        if args.output == "-":
            writer = csv.writer(sys.stdout)
        else:
            out_file = open(args.output, "w", encoding="utf-8", newline="")
            writer = csv.writer(out_file)

        try:
            writer.writerow(("tag", "threshold", args.metric))
            for tag, (threshold, score) in sorted(
                calibrator.best.items(),
                key=lambda item: item[0]
            ):
                threshold = min(1.0, max(0.0, threshold + args.epsilon))
                writer.writerow((tag, f"{threshold:.4f}", f"{score:.4f}"))
        finally:
            if out_file is not None:
                out_file.close()

    main()
