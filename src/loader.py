import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Union
from functools import cached_property

import yaml
from num2words import num2words

import pandas as pd


if getattr(sys, 'frozen', False):
    current_folder = Path(sys.argv[0]).parent
else:
    current_folder = Path(__file__).parent


class Tool:
    def __init__(self, tool: Dict[str, str], artifacts_path, qp):
        self.label = tool['label']
        self.command_line = tool['command-line-cqp'] if qp else tool['command-line']
        self.qp = qp
        self.artifacts_path = artifacts_path if artifacts_path else current_folder

    @cached_property
    def md5(self):
        m = hashlib.md5()
        m.update(self.command_line.replace(' ', '').encode('utf-8', errors='replace'))
        return m.hexdigest()

    @cached_property
    def name(self):
        return f'{self.label}.qp' if self.qp else self.label

    @cached_property
    def folder(self):
        cache = self.artifacts_path / '.cache'
        return cache / f'{self.name}.{self.md5}'

    def __str__(self):
        return self.name


class Stream:
    def __init__(self, stream: Dict[str, str]):
        self.path = Path(stream['stream'])
        self.qp = stream.get('qp', [])
        self.bitrates = stream.get('bitrates', [])

    def br_or_qp(self, tool: Tool):
        return self.qp if tool.qp else self.bitrates

    @cached_property
    def name(self):
        return self.path.name

    def __str__(self):
        return self.name


class DataBank:
    def __init__(self):
        self.tools: List[Tool] = []
        self.streams: List[Stream] = []

        self.common_bitrates = []
        self.common_qp = []
        self.extra_metrics = set(['PSNR'])
        self.per_frame_metrics = set()

        self.df = pd.DataFrame(columns=[
            'tool', 'stream', 'br_or_qp',
            'VMAF',
            'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
            'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
            'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV',
            'real_bitrate'
        ])

        self.details_df = pd.DataFrame(columns=[
            'tool', 'stream', 'br_or_qp', 'frame',
            'VMAF',
            'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
            'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
            'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV',
        ])

    def br_or_qp(self, tool: Tool):
        return self.common_qp if tool.qp else self.common_bitrates

    def add_tool(self, tool: Tool):
        self.tools.append(tool)

    def add_stream(self, stream: Stream):
        self.streams.append(stream)

    def _update_record(self, record: Dict[str, Union[str,float]], metric: str, section: Dict[str,Any]) -> None:
        if metric in section:
            y = section[metric]['Y']
            u = section[metric]['U']
            v = section[metric]['V']
            yuv = (4*y + u + v) / 6
            record.update({
                f'{metric}_Y': y,
                f'{metric}_U': u,
                f'{metric}_V': v,
                f'{metric}_YUV': yuv
            })

    def load_yaml(self, tool: Tool, stream: Stream, br: int, fn: Path):
        with fn.open(encoding='utf8') as f:
            yml = yaml.safe_load(f)

        record = {
            'tool': tool.name,
            'stream': stream.name,
            'br_or_qp': br,
            'real_bitrate': yml['real_bitrate']
        }
        metrics = yml.get('metrics', {})
        if 'VMAF' in metrics:
            record['VMAF'] = metrics['VMAF']

        self._update_record(record, 'PSNR', metrics)
        self._update_record(record, 'SSIM', metrics)
        self._update_record(record, 'MSSIM', metrics)

        self.df = self.df.append(record, ignore_index=True)

    def load_details(self, tool: Tool, stream: Stream, br: int, fn: Path):
        with fn.open(encoding='utf8') as f:
            yml = yaml.safe_load(f)

        records = []
        for i, frame in enumerate(yml):
            record = {
                'tool': tool.name,
                'stream': stream.name,
                'br_or_qp': br,
                'frame': i
            }
            if 'VMAF' in frame:
                record['VMAF'] = frame['VMAF']

            self._update_record(record, 'PSNR', frame)
            self._update_record(record, 'SSIM', frame)
            self._update_record(record, 'MSSIM', frame)

            records.append(record)

        self.details_df = self.details_df.append(pd.DataFrame(records), ignore_index=True)


def load_global_settings(bank:DataBank, cfg:Dict[str,Any]):
    if 'bitrates' in cfg:
        bank.common_bitrates = cfg['bitrates']
    if 'qp' in cfg:
        bank.common_qp = cfg['qp']
    if 'extra-metrics' in cfg:
        bank.extra_metrics.update(metric.upper() for metric in cfg['extra-metrics'])
    if 'per-frame-metrics' in cfg:
        bank.per_frame_metrics.update(metric.upper() for metric in cfg['per-frame-metrics'])


def load_tools(bank: DataBank, tool_section: List[Dict[str,str]], artifacts_path):
    for i, tool in enumerate(tool_section, 1):
        label = tool.get('label')
        if not label:
            sys.exit(f'There is no label in the {num2words(i, ordinal=True)} tool section')
        if 'command-line' in tool:
            bank.add_tool(Tool(tool, artifacts_path, qp=False))
        if 'command-line-cqp' in tool:
            bank.add_tool(Tool(tool, artifacts_path, qp=True))


def load_streams(bank: DataBank, stream_section: List[Dict[str,str]]):
    for stream in stream_section:
        bank.add_stream(Stream(stream))


def load_data(cfg, artifacts_path):
    bank = DataBank()
    load_global_settings(bank, cfg)
    load_tools(bank, cfg.get('tools', []), artifacts_path)
    load_streams(bank, cfg.get('streams', []))

    for tool in bank.tools:
        print(f'{tool.name}')
        bitrates = bank.common_qp if tool.qp else bank.common_bitrates
        for stream in bank.streams:
            print(f'  {stream.name}')
            stream_bitrates = stream.qp if tool.qp else stream.bitrates
            for br in stream_bitrates or bitrates:
                if tool.qp:
                    main_yaml = tool.folder / f'qp-{br}.{stream.name}.yaml'
                    details = tool.folder / f'qp-{br}.{stream.name}.details.yaml'
                else:
                    main_yaml = tool.folder / f'{br}.{stream.name}.yaml'
                    details = tool.folder / f'{br}.{stream.name}.details.yaml'

                if not main_yaml.exists():
                    print(f'"{main_yaml}" does not exists', file=sys.stderr)
                else:
                    bank.load_yaml(tool, stream, br, main_yaml)

                if bank.per_frame_metrics and not details.exists():
                    print(f'"{details}" does not exists', file=sys.stderr)
                elif bank.per_frame_metrics:
                    bank.load_details(tool, stream, br, details)

    return bank
