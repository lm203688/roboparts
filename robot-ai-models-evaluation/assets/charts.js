(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var accent3 = style.getPropertyValue('--accent3').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart 1: Scatter - Parameter Size vs Release Timeline ---
  var scatter = echarts.init(document.getElementById('chart-scatter'), null, { renderer: 'svg' });

  // Data: [month_index, param_size_in_B, name, team, is_chinese, is_new]
  var models = [
    [15, 55, 'RT-2', 'Google', false, false],
    [30, 9, 'RoboFlamingo', 'BIT+MSR', true, false],
    [41, 7, 'OpenVLA', 'Stanford', false, false],
    [41, 0.093, 'Octo', 'UCB', false, false],
    [46, 3, 'pi0', 'Physical\nIntelligence', false, false],
    [54, 0.45, 'SmolVLA', 'Hugging\nFace', false, false],
    [57, 3, 'pi0.5', 'Physical\nIntelligence', false, false],
    [62, 4, 'Kairos 3.0', '大晓/商汤', true, false],
    [66, 5, 'Qwen-Robot', '阿里', true, true],
    [66, 0.05, 'VWA', '拓元+星宸', true, true],
    [65, 7, 'GEN-0', 'Generalist', false, true],
    [65, 0, 'Hy-RxBrain', '腾讯', true, true],
    [65, 4, 'Kairos 3.1', '大晓', true, true],
    [66, 0.89, 'FabriVLA', '优艾智合', true, true],
    [66, 1.5, 'MiniCPM-\nRobot', '面壁智能', true, true],
    [66, 0, 'Hy-VLA-0.5', '腾讯', true, true],
  ];

  var scatterData = models.map(function(m) {
    return {
      value: [m[0], m[1], m[2], m[3], m[4], m[5]],
      symbolSize: Math.max(12, Math.min(40, m[1] * 2 + 8)),
      itemStyle: {
        color: m[5] ? accent : (m[4] ? '#fbbf24' : accent2),
        opacity: m[5] ? 1 : 0.7,
        borderColor: m[5] ? '#fff' : 'transparent',
        borderWidth: m[5] ? 2 : 0
      }
    };
  });

  scatter.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: function(p) {
        var d = p.value;
        var months = ['2025.01','2025.02','2025.03','2025.04','2025.05','2025.06','2025.07','2025.08','2025.09','2025.10','2025.11','2025.12','2026.01','2026.02','2026.03','2026.04','2026.05','2026.06','2026.07'];
        var paramStr = d[1] === 0 ? '未公开' : (d[1] < 1 ? (d[1]*1000).toFixed(0) + 'M' : d[1] + 'B');
        var tag = d[5] ? ' <span style="color:#06b6d4">[NEW]</span>' : '';
        return '<b>' + d[2] + '</b>' + tag + '<br/>' +
          '团队: ' + d[3] + '<br/>' +
          '参数量: ' + paramStr + '<br/>' +
          '发布: ' + months[Math.min(d[0], months.length-1)];
      }
    },
    grid: {
      left: 60,
      right: 30,
      top: 40,
      bottom: 60
    },
    xAxis: {
      name: '发布时间',
      nameLocation: 'center',
      nameGap: 35,
      nameTextStyle: { color: muted, fontSize: 11 },
      type: 'category',
      data: ['2025.01','','','','','2025.06','','','2025.09','','','','2026.01','','','2026.04','','2026.06','2026.07'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, fontSize: 10 },
      axisTick: { show: false },
      splitLine: { show: false }
    },
    yAxis: {
      name: '参数量 (B)',
      nameTextStyle: { color: muted, fontSize: 11 },
      type: 'log',
      min: 0.05,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: {
        color: muted, fontSize: 10,
        formatter: function(v) {
          if (v < 1) return (v * 1000) + 'M';
          return v + 'B';
        }
      },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [{
      type: 'scatter',
      data: scatterData,
      label: {
        show: true,
        formatter: function(p) { return p.value[2]; },
        position: 'right',
        fontSize: 9,
        color: ink,
        distance: 5
      }
    }],
    legend: {
      data: [
        { name: '国际模型', itemStyle: { color: accent2, opacity: 0.7 } },
        { name: '中国模型', itemStyle: { color: '#fbbf24', opacity: 0.7 } },
        { name: '2026新增', itemStyle: { color: accent } }
      ],
      bottom: 5,
      textStyle: { color: muted, fontSize: 10 },
      itemWidth: 12,
      itemHeight: 12
    }
  });
  window.addEventListener('resize', function() { scatter.resize(); });

  // --- Chart 2: Radar - Edge Deployment Capability ---
  var radar = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });

  radar.setOption({
    animation: false,
    tooltip: { appendToBody: true },
    legend: {
      data: ['SmolVLA', 'FabriVLA', 'MiniCPM-Robot', 'Octo', 'GR00T N1.6'],
      bottom: 5,
      textStyle: { color: muted, fontSize: 10 },
      itemWidth: 12,
      itemHeight: 12
    },
    radar: {
      indicator: [
        { name: '参数效率', max: 100 },
        { name: '推理速度', max: 100 },
        { name: '硬件门槛(反向)', max: 100 },
        { name: '开源程度', max: 100 },
        { name: '生态成熟度', max: 100 },
        { name: '中文支持', max: 100 }
      ],
      shape: 'circle',
      splitNumber: 4,
      axisName: { color: muted, fontSize: 10 },
      splitLine: { lineStyle: { color: rule } },
      splitArea: { show: false },
      axisLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: [95, 90, 95, 100, 85, 40],
          name: 'SmolVLA',
          lineStyle: { color: accent },
          areaStyle: { color: accent, opacity: 0.15 },
          itemStyle: { color: accent }
        },
        {
          value: [90, 85, 85, 70, 50, 95],
          name: 'FabriVLA',
          lineStyle: { color: '#fbbf24' },
          areaStyle: { color: '#fbbf24', opacity: 0.1 },
          itemStyle: { color: '#fbbf24' }
        },
        {
          value: [88, 85, 90, 100, 60, 95],
          name: 'MiniCPM-Robot',
          lineStyle: { color: accent3 },
          areaStyle: { color: accent3, opacity: 0.1 },
          itemStyle: { color: accent3 }
        },
        {
          value: [98, 95, 98, 100, 70, 40],
          name: 'Octo',
          lineStyle: { color: accent2 },
          areaStyle: { color: accent2, opacity: 0.1 },
          itemStyle: { color: accent2 }
        },
        {
          value: [65, 65, 40, 60, 95, 50],
          name: 'GR00T N1.6',
          lineStyle: { color: '#ef4444' },
          areaStyle: { color: '#ef4444', opacity: 0.1 },
          itemStyle: { color: '#ef4444' }
        }
      ]
    }]
  });
  window.addEventListener('resize', function() { radar.resize(); });
})();
