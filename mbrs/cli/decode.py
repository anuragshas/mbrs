#!/usr/bin/env python3

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser, FileType, Namespace

from tabulate import tabulate, tabulate_formats
from tqdm import tqdm

from mbrs import registry, timer
from mbrs.decoders import DecoderReferenceBased, DecoderReferenceless, get_decoder
from mbrs.metrics import Metric, get_metric


def parse_args() -> Namespace:
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    # fmt: off
    parser.add_argument("hypotheses", help="Hypotheses file.")
    parser.add_argument("--source", "-s", help="Source file.")
    parser.add_argument("--references", "-r", help="References file.")
    parser.add_argument("--output", "-o", action="store",
                        default="-", type=FileType("w"),
                        help="Output file.")
    parser.add_argument("--num-candidates", "--nc", "-n", type=int, required=True,
                        help="Number of candidates.")
    parser.add_argument("--num-references", "--nr", type=int,
                        help="Number of references for each sentence.")
    parser.add_argument("--decoder", "-d", type=str, default="mbr",
                        choices=registry.get_registry("decoder").keys(),
                        help="Decoder type.")
    parser.add_argument("--metric", "-m", type=str, default="bleu",
                        choices=registry.get_registry("metric").keys(),
                        help="Metric type.")
    parser.add_argument("--nbest", type=int, default=1,
                        help="N-best.")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="No report.")
    parser.add_argument("--report", type=str, default="rounded_outline",
                        choices=tabulate_formats,
                        help="Report runtime statistics.")
    parser.add_argument("--width", "-w", type=int, default=1,
                        help="Number of digits for values of float point.")
    comet_parser = parser.add_argument_group("COMET")
    comet_parser.add_argument("--batch-size", "-b", type=int, default=64,
                              help="Batch size.")
    comet_parser.add_argument("--fp16", action="store_true",
                              help="Use float16.")
    # fmt: on
    return parser.parse_args()


def main(args: Namespace) -> None:

    sources = None
    if args.source is not None:
        with open(args.source, mode="r") as f:
            sources = f.readlines()

    with open(args.hypotheses, mode="r") as f:
        hypotheses = f.readlines()

    references = None
    if args.references is not None:
        with open(args.references, mode="r") as f:
            references = f.readlines()
    else:
        references = hypotheses

    metric_type = get_metric(args.metric)
    if args.metric == "comet" or args.metric == "cometqe":
        metric_cfg = metric_type.Config(batch_size=args.batch_size, float16=args.fp16)
    else:
        metric_cfg = metric_type.Config()
    metric: Metric = metric_type(metric_cfg)

    decoder_type = get_decoder(args.decoder)
    decoder: DecoderReferenceBased | DecoderReferenceless = decoder_type(
        decoder_type.Config(), metric
    )

    num_cands = args.num_candidates
    num_refs = args.num_references or num_cands
    num_sents = len(hypotheses) // args.num_candidates
    assert num_sents * num_cands == len(hypotheses)

    if isinstance(decoder, DecoderReferenceless):
        for i in tqdm(range(num_sents)):
            src = sources[i].strip()
            hyps = [h.strip() for h in hypotheses[i * num_cands : (i + 1) * num_cands]]
            with timer.measure("total"):
                output = decoder.decode(hyps, src, args.nbest)
            for sent in output.sentence:
                print(sent, file=args.output)
    else:
        for i in tqdm(range(num_sents)):
            src = sources[i].strip() if sources is not None else None
            hyps = [h.strip() for h in hypotheses[i * num_cands : (i + 1) * num_cands]]
            refs = [r.strip() for r in references[i * num_refs : (i + 1) * num_refs]]
            with timer.measure("total"):
                output = decoder.decode(hyps, refs, src, args.nbest)
            for sent in output.sentence:
                print(sent, file=args.output)

    if not args.quiet:
        statistics = timer.aggregate().result(num_sents)
        table = tabulate(
            statistics, headers="keys", tablefmt=args.report, floatfmt=f".{args.width}f"
        )
        print(table)


def cli_main():
    args = parse_args()
    main(args)


if __name__ == "__main__":
    cli_main()
