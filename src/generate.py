import sys
import argparse
from pathlib import Path

import yaml

from loader import load_data
from charts import generate_charts


if getattr(sys, 'frozen', False):
    current_folder = Path(sys.argv[0]).parent
else:
    current_folder = Path(__file__).parent

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Zero-config chart generator")
    parser.add_argument('config', nargs='?', default='edc.yaml',
                        help='configuration file in yaml format')

    args = parser.parse_args()

    config = Path(args.config)
    if not config.is_absolute():
        config = current_folder / config

    if not config.exists():
        sys.exit(f'Configuration file "{config}" not found')

    with config.open(encoding='utf8') as f:
        cfg = yaml.safe_load(f)

    bank = load_data(cfg)

    generate_charts(bank)
