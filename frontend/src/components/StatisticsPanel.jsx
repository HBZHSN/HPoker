import React from 'react';

const luckDimensions = [
  ['starting', '起手牌运', '35%'],
  ['board', '公共牌运', '25%'],
  ['matchup', '对位牌运', '20%'],
  ['all_in', '全下兑现', '20%'],
];

const metrics = [
  ['vpip', 'VPIP', '翻牌前主动投入筹码的手数 / 已完成手数'],
  ['pfr', 'PFR', '翻牌前加注的手数 / 已完成手数'],
  ['three_bet', '3Bet', '翻牌前首次再加注的手数 / 有再加注机会的手数'],
  ['win_rate', '胜率', '净赢筹码的手数 / 已完成手数'],
  ['collect_rate', '收池率', '获得奖池（含平分）的手数 / 已完成手数；不含单纯退回下注'],
  ['showdown_rate', '摊牌率', '参与摊牌的手数 / 已完成手数'],
];

export default function StatisticsPanel({ data }) {
  return <>
            <p className="text-xs text-slate-400 mb-3">已完成 {data.hands} 手{data.hands < 30 ? ' · 样本较少' : ''}</p>
            <div className="grid grid-cols-3 gap-2">
              {metrics.map(([key, label, help]) => <div key={key} title={help} className="rounded-xl border border-slate-800 bg-slate-900/60 px-2 py-3 text-center">
                <p className="text-xs text-slate-400 mb-1">{label}</p><p className="font-bold text-lg tabular-nums">{data[key] == null ? '—' : `${data[key]}%`}</p>
              </div>)}
            </div>
            <div className="mt-3 rounded-xl border border-amber-500/25 bg-amber-950/15 p-3">
              <div className="flex justify-between items-baseline"><span className="text-sm text-amber-200">综合牌运</span><span className="text-xl font-bold text-amber-300">{data.luck}<span className="text-xs text-slate-500"> / 100</span></span></div>
              <div className="relative h-1.5 rounded-full bg-slate-800 my-2"><div className="h-full rounded-full bg-gradient-to-r from-slate-500 to-amber-400" style={{ width: `${data.luck}%` }} /><span className="absolute left-1/2 top-0 h-full w-px bg-white/60" /></div>
              <p className="text-xs text-slate-400">{data.luck_samples ? `${data.luck_samples} 手起手样本 · 50 为中性` : '暂无有效样本 · 暂记中性 50'}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {luckDimensions.map(([key, label, weight]) => {
                  const dimension = data.luck_dimensions?.[key];
                  return <div key={key} className="rounded-lg bg-slate-950/50 p-2">
                    <div className="flex justify-between gap-2 text-xs"><span className="text-slate-300">{label}</span><span className="text-slate-500">{weight}</span></div>
                    <div className="mt-1 flex items-baseline justify-between gap-2"><span className="font-bold tabular-nums text-amber-200">{dimension?.score ?? 50}</span><span className="text-[10px] text-slate-400">{dimension?.samples ? `${dimension.samples} 手` : '暂无样本'}</span></div>
                  </div>;
                })}
              </div>
            </div>
            <details className="mt-4 text-xs text-slate-400 leading-relaxed">
              <summary className="cursor-pointer py-1">统计口径</summary>
              <div className="mt-2 space-y-2">
                {metrics.map(([key, label, help]) => <p key={key}>{label}：{help}。</p>)}
                <p>3Bet 机会 {data.three_bet_opportunities} 手。无分母时显示 —，当前未结束的手牌不计入。</p>
                <p>综合牌运以起手 35%、公共牌 25%、对位 20%、全下 20% 为基础权重；无样本维度显示 50，但不参与总分。50 为中性，越高表示在当前样本规模下更偏好运。</p>
                <p>起手牌运：按全部 1,326 种组合加权的起手强度百分位；包含弃牌和未亮底牌。本桌公开展示完整分数及四维统计，每手结束后更新。</p>
                <p>公共牌运：仍在参与时，实际公共牌下对随机对手的牌力减去起手预期；弃牌后的发牌不计入。</p>
                <p>对位牌运：完整公开摊牌时，实际比牌份额减去面对同人数随机对手的预期份额，反映大牌相撞等对位结果。</p>
                <p>全下兑现：主池、边池分别比较下注与资格锁定时的理论份额和最终份额；按底池 BB 数的平方根加权，上限 4。退款、河牌后投入不计，双牌面取平均，平局平分；不计奇数筹码和辅助折让。</p>
                <p>先将累计好运或坏运除以其波动规模（逐手差值平方和加中性先验，再开平方），再映射到 0–100。总分按基础权重组合标准化信号，并计入同一手各维度的相关性，避免一次好运重复放大；因此总分不是四个显示分数的简单平均。</p>
                <p>少量样本保留中性先验；手数增加后比较偏离随机预期的程度，不再机械回归 50。80 分不表示超过 80% 玩家，也不是下一手 80% 胜率。</p>
              <p>这是描述已记录样本的估算指数，仍受参与和摊牌选择影响，不代表技术或净盈利。历史按原始统计量重新汇总，记录缺失的维度不补造样本。</p>
              </div>
            </details>
  </>;
}
