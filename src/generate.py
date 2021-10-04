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
    parser.add_argument('config', nargs='?', default='edc.yaml', help='configuration file in yaml format.'
                                                            ' (default: %(default)s)')
    parser.add_argument('--artifacts', required=False, help='Path to edc output artifacts directory.'
                                                            ' (default: the same directory as config\'s one)')
    parser.add_argument('--charts', required=False, help='Path to output charts directory.'
                                                            ' (default: the charts directory)')

    args = parser.parse_args()

    config = Path(args.config)
    if not config.is_absolute():
        config = current_folder / config

    if not config.exists():
        sys.exit(f'Configuration file "{config}" not found')

    with config.open(encoding='utf8') as f:
        cfg = yaml.safe_load(f)

    # where .cache and other artifacts are located
    artifacts_path = None
    if args.artifacts:
        artifacts_path = Path(args.artifacts)
        if not artifacts_path.exists():
            exit(f'Artifacts path not found: {artifacts_path}')

    charts_path = None
    if args.charts:
        charts_path = Path(args.charts)


    bank = load_data(cfg, artifacts_path)

    generate_charts(bank, charts_path)
