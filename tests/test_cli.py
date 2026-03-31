from serialhub.cli import build_parser


def test_parser_accepts_commands() -> None:
    parser = build_parser()
    args_run = parser.parse_args(["run"])
    args_update = parser.parse_args(["update"])

    assert args_run.command == "run"
    assert args_update.command == "update"
