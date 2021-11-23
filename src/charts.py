import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List, Any

import jinja2
import altair as alt
from loader import DataBank, Stream


if getattr(sys, 'frozen', False):
    current_folder = Path(sys.argv[0]).parent
else:
    current_folder = Path(__file__).parent


@dataclass
class Chart:
    metric: str
    data: str


template = '''
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-lite@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
  <script src="https://code.jquery.com/jquery-3.6.0.slim.min.js" integrity="sha256-u7e5khyithlIdTpu22PHhENmPcRdFiHRjhAuHcs05RI=" crossorigin="anonymous"></script>
  <style>
    body { font: 11pt Calibri,"Helvetica Neue",Arial,sans-serif; }
    label { margin-right: 2px; }
    .component-list { padding: 0; margin: 0; }
    .header    { display: inline-block; }
    .component { padding: 0 2px; margin: 0;  display: inline-block; cursor: pointer; }
    .active-component { background-color: #ccc; }
  </style>
<script>
let availableMetrics = {{ available_metrics }};
let hadVMAF = false;

const embed_opt = {"mode": "vega-lite"};
const mean_charts = {};
const worst_charts = {};
const frame_charts = {};
const frame_size_charts = {};

const qps = {{ qps }};
const bitrates = {{ bitrates }};
let selectedOption = null;

function fillChartsData() {
{% for chart in mean_charts -%}
mean_charts.{{chart.metric}} = {{chart.data}};
{% endfor %}

{% for chart in worst_charts -%}
worst_charts.{{chart.metric}} = {{chart.data}};
{% endfor %}

{% for chart in frame_charts -%}
frame_charts.{{chart.metric}} = {{chart.data}};
{% endfor %}

{% for chart in frame_sizes_charts -%}
frame_size_charts.{{chart.metric}} = {{chart.data}};
{% endfor %}
}

function createDivs() {
    for(const metric of availableMetrics) {
        $(`<div id="mean_${metric}"></div>`).appendTo('div.mean');
        $(`<div id="worst_${metric}"></div>`).appendTo('div.worst');
        $(`<div id="frame_${metric}"></div>`).appendTo('div.frame');
    }
}

function attachComponentListeners() {
    $('.component').click(function() {
        const $el = $(this);
        if ($el.hasClass('active-component')) return;
        $('.component-list > .component').removeClass('active-component');
        $el.addClass('active-component');
        const component = $el.data('component');

        for(const metric of availableMetrics) {
            vegaEmbed(`#mean_${metric}`, mean_charts[`${metric}_${component}`], embed_opt);
            vegaEmbed(`#worst_${metric}`, worst_charts[`${metric}_${component}`], embed_opt);
            vegaEmbed(`#frame_${metric}`, frame_charts[`${metric}_${component}_${selectedOption}`], embed_opt);
        }
    });
}

function changeHandler() {
    const selectedValue = $( "#br_and_qps option:selected" ).val();
    for(const metric of availableMetrics) {
        if (hadVMAF) {
            vegaEmbed('#frame_VMAF', frame_charts[`VMAF_${selectedValue}`], embed_opt);
        }
        const component = $('.component.active-component').data('component')
        vegaEmbed(`#frame_${metric}`, frame_charts[`${metric}_${component}_${selectedValue}`], embed_opt);
        if (!jQuery.isEmptyObject(frame_size_charts)) {
            vegaEmbed('#frame_size', frame_size_charts[`frame_size_${selectedValue}`], embed_opt);
        }

    }
}

$(function() {
    createDivs();
    attachComponentListeners();
    fillChartsData();
    selectedOption = qps.length ? qps[0] : bitrates[0];
    if (!jQuery.isEmptyObject(frame_size_charts)) {
        vegaEmbed('#frame_size', frame_size_charts[`frame_size_${selectedOption}`], embed_opt);
    }
    for (const metric of availableMetrics) {
        if (metric === 'VMAF') {
            vegaEmbed('#mean_VMAF', mean_charts.VMAF, embed_opt);
            if (!jQuery.isEmptyObject(frame_charts)) {
                vegaEmbed('#worst_VMAF', worst_charts.VMAF, embed_opt);
                vegaEmbed('#frame_VMAF', frame_charts[`VMAF_${selectedOption}`], embed_opt);
            }
        } else {
            vegaEmbed(`#mean_${metric}`, mean_charts[`${metric}_Y`], embed_opt);
            if (!jQuery.isEmptyObject(frame_charts)) {
                vegaEmbed(`#worst_${metric}`, worst_charts[`${metric}_Y`], embed_opt);
                vegaEmbed(`#frame_${metric}`, frame_charts[`${metric}_Y_${selectedOption}`], embed_opt);
            }
        }
    }
    if (!jQuery.isEmptyObject(frame_charts)) {
        $("<label for='br_and_qps'>Bitrates and QPs</label>").appendTo("div#controls");

        const select = $("<select name='br_and_qps' id='br_and_qps'></select>")
        for (const qp of qps) {
            if (qp === selectedOption) {
                $(`<option selected value="${qp}">QP: ${qp}</option>`).appendTo(select);
            } else {
                $(`<option value="${qp}">QP: ${qp}</option>`).appendTo(select);
            }
        }
        for (const br of bitrates) {
            if (br === selectedOption) {
                $(`<option selected value="${br}">${br}</option>`).appendTo(select);
            } else {
                $(`<option value="${br}">${br}</option>`).appendTo(select);
            }
        }
        select.appendTo("div#controls");
        select.change(changeHandler);
    }

    hadVMAF = availableMetrics.includes('VMAF');
    availableMetrics = availableMetrics.filter(metric => metric !== 'VMAF');
})
</script>
</head>
<body>
<ul class='component-list'>
    <li class='header'>Components:</li>
    <li class='component active-component' data-component='Y'>Y</li>
    <li class='component' data-component='U'>U</li>
    <li class='component' data-component='V'>V</li>
    <li class='component' data-component='YUV'>YUV</li>
</ul>
<div class="mean"></div>
<div class="worst"></div>
<div id="controls"></div>
<div class="frame"></div>
<div id="frame_size"></div>
</body>
</html>
'''


def compact_json(source: str) -> str:
    jsn = json.loads(source)
    return json.dumps(jsn, separators=(',', ':'))


def generate_mean_charts(bank: DataBank, stream: Stream) -> Dict[str,Any]:
    charts = []

    df = bank.df.query(f"stream == '{stream.name}'")
    for metric in ['PSNR', 'SSIM', 'MSSIM']:
        if metric in bank.extra_metrics:
           for component in ['Y', 'U', 'V', 'YUV']:
                columns = set(['stream', 'VMAF',
                    'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
                    'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
                    'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
                ])
                columns.discard(f'{metric}_{component}')
                metric_df = df.drop(columns=columns)
                tooltip_format = '.2f' if metric == 'PSNR' else '.4f'
                selection = alt.selection_multi(fields=['tool'], bind='legend')
                chart = Chart(f'{metric}_{component}', alt.Chart(metric_df).mark_line(point=True, interpolate='monotone').encode(
                    alt.X('real_bitrate', scale=alt.Scale(zero=False), title='Bitrate (Kb/s)'),
                    alt.Y(f'{metric}_{component}', scale=alt.Scale(zero=False), title=f'Mean {metric} {component}'),
                    color='tool',
                    tooltip=[
                        alt.Tooltip('real_bitrate:Q', format=',.1f', title='Bitrate'),
                        alt.Tooltip(f'{metric}_{component}:Q', format=tooltip_format, title=f'{metric} {component}')
                    ],
                    opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
                ).configure_legend(
                    orient='top'
                ).interactive().add_selection(
                    selection
                ).to_json())

                chart.data = compact_json(chart.data)
                charts.append(chart)

    if 'VMAF' in bank.extra_metrics:
        vmaf_df = df.drop(columns=[
            'stream',
            'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
            'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
            'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
        ])
        selection = alt.selection_multi(fields=['tool'], bind='legend')
        chart = Chart('VMAF', alt.Chart(vmaf_df).mark_line(point=True, interpolate='monotone').encode(
            alt.X('real_bitrate', scale=alt.Scale(zero=False), title='Bitrate (Kb/s)'),
            alt.Y('VMAF', scale=alt.Scale(zero=False), title='Mean VMAF'),
            color='tool',
            tooltip=[
                alt.Tooltip('real_bitrate:Q', format=',.1f', title='Bitrate'),
                alt.Tooltip('VMAF:Q', format='.1f')
            ],
            opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
        ).configure_legend(
            orient='top'
        ).interactive().add_selection(
            selection
        ).to_json())

        chart.data = compact_json(chart.data)
        charts.append(chart)

    return charts


def generate_worst_charts(bank: DataBank, stream: Stream) -> Dict[str,Any]:
    charts = []

    stream_df = bank.df.query(f'stream == "{stream.name}"')
    stream_df = stream_df.drop(columns=[
        'stream', 'VMAF',
        'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
        'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
        'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
    ]).set_index(['tool', 'br_or_qp'])

    df = bank.details_df.query(f'stream == "{stream.name}"')
    for metric in ['PSNR', 'SSIM', 'MSSIM']:
        if metric in bank.extra_metrics:
           for component in ['Y', 'U', 'V', 'YUV']:
                columns = set(['stream', 'VMAF',
                    'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
                    'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
                    'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
                ])
                columns.discard(f'{metric}_{component}')
                metric_details_df = df.drop(columns=columns)

                worst_metric = metric_details_df.groupby(['tool', 'br_or_qp']).min().reset_index()
                worst_metric = stream_df.join(worst_metric.set_index(['tool', 'br_or_qp'])).reset_index()

                tooltip_format = '.2f' if metric == 'PSNR' else '.4f'
                selection = alt.selection_multi(fields=['tool'], bind='legend')
                chart = Chart(f'{metric}_{component}', alt.Chart(worst_metric).mark_line(point=True, interpolate='monotone').encode(
                    alt.X('real_bitrate', scale=alt.Scale(zero=False), title='Bitrate (Kb/s)'),
                    alt.Y(f'{metric}_{component}', scale=alt.Scale(zero=False), title=f'Worst {metric} {component}'),
                    color='tool',
                    tooltip=[
                        alt.Tooltip('real_bitrate:Q', format=',.1f', title='Bitrate'),
                        alt.Tooltip(f'{metric}_{component}:Q', format=tooltip_format, title=f'{metric} {component}')
                    ],
                    opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
                ).configure_legend(
                    orient='top'
                ).interactive().add_selection(
                    selection
                ).to_json())

                chart.data = compact_json(chart.data)
                charts.append(chart)


    if 'VMAF' in bank.extra_metrics:
        vmaf_details_df = df.drop(columns=[
            'stream', 'frame',
            'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
            'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
            'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
        ])

        worst_wmaf = vmaf_details_df.groupby(['tool', 'br_or_qp']).min().reset_index()
        worst_wmaf = stream_df.join(worst_wmaf.set_index(['tool', 'br_or_qp'])).reset_index()
        selection = alt.selection_multi(fields=['tool'], bind='legend')
        chart = Chart('VMAF', alt.Chart(worst_wmaf).mark_line(point=True, interpolate='monotone').encode(
            alt.X('real_bitrate', scale=alt.Scale(zero=False), title='Bitrate (Kb/s)'),
            alt.Y('VMAF', scale=alt.Scale(zero=False), title='Worst VMAF'),
            color='tool',
            tooltip=[
                alt.Tooltip('real_bitrate:Q', format=',.1f', title='Bitrate'),
                alt.Tooltip('VMAF:Q', format='.1f')
            ],
            opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
        ).configure_legend(
            orient='top'
        ).interactive().add_selection(
            selection
        ).to_json())

        chart.data = compact_json(chart.data)
        charts.append(chart)

    return charts

def generate_frame_size_charts(bank: DataBank, stream: Stream) -> Dict[str,Any]:
    charts = []
    for tool in bank.tools:
        br_or_qp = stream.br_or_qp(tool) or bank.br_or_qp(tool)

        for qp in br_or_qp:
            df = bank.details_df.query(f'stream == "{stream.name}" and br_or_qp == {qp}')
            columns = set(['stream', 'VMAF',
                'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
                'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
                'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
            ])
            metric_details_df = df.drop(columns=columns)
            selection = alt.selection_multi(fields=['tool'], bind='legend')
            chart = Chart(
                f'frame_size_{qp}',
                alt.Chart(metric_details_df).mark_line(
                    point=True, interpolate='monotone'
                ).encode(
                    alt.X('frame'),
                    alt.Y(
                        'frame_size',
                        scale=alt.Scale(zero=False),
                        title='frame size'
                    ),
                    color='tool',
                    tooltip=[
                        alt.Tooltip('frame:Q'),
                        alt.Tooltip('frame_size:Q'),
                        alt.Tooltip('br_or_qp:Q', title='Bitrate or QP'),
                    ],
                    opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
            ).properties(
                width=1450
            ).interactive().add_selection(
                selection
            ).to_json())

            chart.data = compact_json(chart.data)
            charts.append(chart)

    return charts

def generate_frame_charts(bank: DataBank, stream: Stream) -> Tuple[List[int],List[int],Dict[str,Any]]:
    charts = []
    bitrates = []
    qps = []
    for tool in bank.tools:
        br_or_qp = stream.br_or_qp(tool) or bank.br_or_qp(tool)

        if tool.qp:
            qps = br_or_qp
        else:
            bitrates = br_or_qp

        for qp in br_or_qp:
            df = bank.details_df.query(f'stream == "{stream.name}" and br_or_qp == {qp}')
            for metric in ['PSNR', 'SSIM', 'MSSIM']:
                if metric in bank.extra_metrics:
                    for component in ['Y', 'U', 'V', 'YUV']:
                        columns = set(['stream', 'VMAF', 'frame_size',
                            'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
                            'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
                            'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
                        ])
                        columns.discard(f'{metric}_{component}')
                        metric_details_df = df.drop(columns=columns)
                        selection = alt.selection_multi(fields=['tool'], bind='legend')
                        tooltip_format = '.2f' if metric == 'PSNR' else '.4f'
                        chart = Chart(
                            f'{metric}_{component}_{qp}',
                            alt.Chart(metric_details_df).mark_line(
                                point=True, interpolate='monotone'
                            ).encode(
                                alt.X('frame'),
                                alt.Y(
                                    f'{metric}_{component}',
                                    scale=alt.Scale(zero=False),
                                    title=f'{metric} {component}'
                                ),
                                color='tool',
                                tooltip=[
                                    alt.Tooltip('frame:Q'),
                                    alt.Tooltip(
                                        f'{metric}_{component}:Q',
                                        format=tooltip_format,
                                        title=f'{metric} {component}'
                                    ),
                                    alt.Tooltip('br_or_qp:Q', title='Bitrate or QP'),
                                ],
                                opacity=alt.condition(selection, alt.value(1), alt.value(0.1)
                            )
                        ).properties(
                            width=1450
                        ).interactive().add_selection(
                            selection
                        ).to_json())

                        jsn = json.loads(chart.data)
                        chart.data = json.dumps(jsn, separators=(',', ':'))
                        charts.append(chart)

            if 'VMAF' in bank.extra_metrics:
                vmaf_details_df = df.drop(columns=[
                    'stream', 'frame_size',
                    'PSNR_Y', 'PSNR_U', 'PSNR_V', 'PSNR_YUV',
                    'SSIM_Y', 'SSIM_U', 'SSIM_V', 'SSIM_YUV',
                    'MSSIM_Y', 'MSSIM_U', 'MSSIM_V', 'MSSIM_YUV'
                ])

                selection = alt.selection_multi(fields=['tool'], bind='legend')

                chart = Chart(f'VMAF_{qp}', alt.Chart(vmaf_details_df).mark_line(point=True, interpolate='monotone').encode(
                    alt.X('frame'),
                    alt.Y('VMAF', scale=alt.Scale(zero=False)),
                    color='tool',
                    tooltip=[
                        alt.Tooltip('frame:Q'),
                        alt.Tooltip('VMAF:Q', format='.1f'),
                        alt.Tooltip('br_or_qp:Q', title='Bitrate or QP'),
                    ],
                    opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
                ).properties(
                    width=1450
                ).interactive().add_selection(
                    selection
                ).to_json())

                chart.data = compact_json(chart.data)
                charts.append(chart)

    return bitrates, qps, charts

def generate_charts(bank: DataBank, charts_folder):
    alt.data_transformers.disable_max_rows()
    if not charts_folder:
        charts_folder = current_folder / 'charts'
    charts_folder.mkdir(exist_ok=True)

    # loader = jinja2.FileSystemLoader(searchpath=current_folder)
    # env = jinja2.Environment(loader=loader)
    # t = env.get_template('template.html')
    env = jinja2.Environment()
    t = env.from_string(template)

    for stream in bank.streams:
        fn = Path(stream.name).with_suffix(f'{stream.path.suffix}.html')
        mean_charts = generate_mean_charts(bank, stream)

        worst_charts = {} if bank.details_df.empty else generate_worst_charts(bank, stream)

        frame_charts = {}
        bitrates = []
        qps = []
        if not bank.details_df.empty:
            bitrates, qps, frame_charts = generate_frame_charts(bank, stream)

        frame_sizes_charts = {}
        if bank.has_file_sizes:
            frame_sizes_charts = generate_frame_size_charts(bank, stream)

        html = t.render(
            mean_charts=mean_charts,
            worst_charts=worst_charts,
            frame_charts=frame_charts,
            frame_sizes_charts=frame_sizes_charts,
            bitrates=bitrates,
            qps=qps,
            available_metrics=list(bank.extra_metrics)
        )
        (charts_folder / fn).write_text(html)
