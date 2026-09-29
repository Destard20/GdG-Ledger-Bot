import tempfile
from pathlib import Path
from bot.custom_commands import load_custom_commands, build_bot_commands_list


def test_load_custom_commands_from_yaml():
    with tempfile.TemporaryDirectory() as tmpdir:
        caffe_path = Path(tmpdir) / "caffe.yaml"
        caffe_path.write_text(
            """
command: "caffe"
description: "Caffè veloce"
defaults:
  date_time: "now"
  method: "Contanti"
  flow: "Uscita"
  amount: 1.20
  description: "Caffè al bar"
""",
            encoding="utf-8"
        )

        cmds = load_custom_commands(tmpdir)
        assert "caffe" in cmds
        cfg = cmds["caffe"]
        assert cfg.command == "caffe"
        assert cfg.description == "Caffè veloce"
        assert cfg.defaults.date_time == "now"
        assert cfg.defaults.method == "Contanti"
        assert cfg.defaults.flow == "Uscita"
        assert cfg.defaults.amount == 1.20
        assert cfg.defaults.description == "Caffè al bar"


def test_build_bot_commands_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "merenda.yaml"
        file_path.write_text(
            """
command: "merenda"
description: "Acquisto merenda"
""",
            encoding="utf-8"
        )
        cmds = load_custom_commands(tmpdir)
        bot_cmds = build_bot_commands_list(cmds)
        names = [c.command for c in bot_cmds]

        assert "write" in names
        assert "w" in names
        assert "help" in names
        assert "cancel" in names
        assert "merenda" in names


def test_custom_command_prefix_suffix():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "quota.yaml"
        file_path.write_text(
            """
command: "quota"
description: "Quota socio con prefisso"
defaults:
  description_prefix: "Quota: "
  description_suffix: " [2026]"
""",
            encoding="utf-8"
        )
        cmds = load_custom_commands(tmpdir)
        cfg = cmds["quota"]
        assert cfg.defaults.description_prefix == "Quota: "
        assert cfg.defaults.description_suffix == " [2026]"

